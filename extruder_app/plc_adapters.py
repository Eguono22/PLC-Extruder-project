"""PLC communication adapters for the extruder application."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from plc_extruder.controller import ExtruderController
from plc_extruder.utils.alarms import Alarm, AlarmSeverity

try:
    from asyncua import Client
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    Client = None

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    ModbusTcpClient = None


class BasePlcAdapter(ABC):
    """Common interface for simulation and PLC-backed data sources."""

    mode_name = "base"

    @abstractmethod
    def scan(self) -> None:
        """Advance or poll the underlying control source."""

    @abstractmethod
    def start(self) -> bool:
        """Start the machine sequence."""

    @abstractmethod
    def stop(self) -> bool:
        """Stop the machine sequence."""

    @abstractmethod
    def reset(self) -> bool:
        """Reset alarms and return to idle."""

    @abstractmethod
    def emergency_stop(self) -> None:
        """Force an immediate emergency stop."""

    @abstractmethod
    def acknowledge_alarms(self) -> int:
        """Acknowledge active alarms."""

    @abstractmethod
    def set_recipe(
        self,
        feed_rate_kg_h: float,
        screw_rpm: float,
        zone_setpoints_c: Optional[List[float]] = None,
        die_setpoint_c: Optional[float] = None,
    ) -> None:
        """Apply recipe and setpoint data."""

    @abstractmethod
    def status_snapshot(self) -> Dict[str, object]:
        """Return a complete machine snapshot."""

    @abstractmethod
    def active_alarms(self) -> List[Alarm]:
        """Return active alarms."""

    def close(self) -> None:
        """Release any adapter resources."""

    def diagnostics(self) -> Dict[str, object]:
        """Return adapter-specific connectivity diagnostics."""
        return {
            "plc_mode": self.mode_name,
            "connected": True,
            "endpoint": "",
            "node_prefix": "",
            "last_error": "",
            "last_poll_succeeded": True,
        }

    def browse_nodes(self, node_id: Optional[str] = None) -> List[Dict[str, str]]:
        """Browse PLC nodes when supported by the adapter."""
        return []


class SimulationPlcAdapter(BasePlcAdapter):
    """Adapter that uses the in-repo Python simulation as the control source."""

    mode_name = "simulation"

    def __init__(self) -> None:
        self.controller = ExtruderController()

    def scan(self) -> None:
        self.controller.scan()

    def start(self) -> bool:
        return self.controller.start()

    def stop(self) -> bool:
        return self.controller.stop()

    def reset(self) -> bool:
        return self.controller.reset()

    def emergency_stop(self) -> None:
        self.controller.emergency_stop()

    def acknowledge_alarms(self) -> int:
        return self.controller.acknowledge_alarms()

    def set_recipe(
        self,
        feed_rate_kg_h: float,
        screw_rpm: float,
        zone_setpoints_c: Optional[List[float]] = None,
        die_setpoint_c: Optional[float] = None,
    ) -> None:
        self.controller.set_recipe(feed_rate=feed_rate_kg_h, screw_rpm=screw_rpm)
        if zone_setpoints_c:
            for idx, temp in enumerate(zone_setpoints_c[: self.controller.heater.zone_count]):
                self.controller.heater.set_setpoint(idx, temp)
        if die_setpoint_c is not None:
            self.controller.die.set_setpoint(die_setpoint_c)

    def status_snapshot(self) -> Dict[str, object]:
        snapshot = self.controller.status_dict()
        snapshot["active_alarms"] = [
            {
                "code": alarm.code,
                "message": alarm.message,
                "severity": alarm.severity.name,
                "timestamp": alarm.timestamp,
                "acknowledged": alarm.acknowledged,
            }
            for alarm in self.controller.alarms.active_alarms
        ]
        return snapshot

    def active_alarms(self) -> List[Alarm]:
        return self.controller.alarms.active_alarms

    def diagnostics(self) -> Dict[str, object]:
        return {
            "plc_mode": self.mode_name,
            "connected": True,
            "endpoint": "simulation://local",
            "node_prefix": "",
            "last_error": "",
            "last_poll_succeeded": True,
        }


class OpcUaPlcAdapter(BasePlcAdapter):
    """OPC UA-backed PLC adapter for TwinCAT-style extruder tags."""

    mode_name = "opcua"

    def __init__(
        self,
        endpoint: str,
        node_prefix: str = "ns=2;s=",
        timeout_s: float = 5.0,
    ) -> None:
        if Client is None:
            raise RuntimeError(
                "The asyncua package is required for OPC UA mode. "
                "Install dependencies from requirements.txt first."
            )
        self.endpoint = endpoint
        self.node_prefix = node_prefix
        self.timeout_s = timeout_s
        self._connected = False
        self._last_snapshot = self._empty_snapshot()
        self._cached_alarms: List[Alarm] = []
        self._last_error = ""
        self._last_poll_succeeded = False

    def _node(self, suffix: str) -> str:
        return f"{self.node_prefix}{suffix}"

    def _read_map(self) -> Dict[str, str]:
        return {
            "state": self._node("gExtruderStatus.State"),
            "scan_number": self._node("gExtruderStatus.ScanNumber"),
            "run_time_s": self._node("gExtruderStatus.RunTime_s"),
            "safety_state": self._node("gExtruderStatus.SafetyState"),
            "alarm_summary": self._node("gExtruderStatus.AlarmSummary.AlarmWord"),
            "alarm_any": self._node("gExtruderStatus.AnyAlarm"),
            "alarm_warning": self._node("gExtruderStatus.AnyWarning"),
            "heater_all_at_setpoint": self._node("gExtruderStatus.HeaterAllAtSetpoint"),
            "die_at_setpoint": self._node("gExtruderStatus.DieAtSetpoint"),
            "feed_rate_setpoint": self._node("gExtruderStatus.FeedRateSetpointKgH"),
            "screw_rpm_setpoint": self._node("gExtruderStatus.ScrewRpmSetpoint"),
            "zone1_sp": self._node("gExtruderStatus.Zone1Setpoint_C"),
            "zone2_sp": self._node("gExtruderStatus.Zone2Setpoint_C"),
            "zone3_sp": self._node("gExtruderStatus.Zone3Setpoint_C"),
            "zone4_sp": self._node("gExtruderStatus.Zone4Setpoint_C"),
            "die_sp": self._node("gExtruderStatus.DieSetpoint_C"),
            "recipe_name": self._node("gExtruderStatus.ActiveRecipeName"),
            "zone1_temp": self._node("gExtruderAI.Zone1Temp_C"),
            "zone2_temp": self._node("gExtruderAI.Zone2Temp_C"),
            "zone3_temp": self._node("gExtruderAI.Zone3Temp_C"),
            "zone4_temp": self._node("gExtruderAI.Zone4Temp_C"),
            "die_temp": self._node("gExtruderAI.DieTemp_C"),
            "pressure_bar": self._node("gExtruderAI.MeltPressure_bar"),
            "motor_rpm": self._node("gExtruderAI.MotorRpm"),
            "motor_current": self._node("gExtruderAI.MotorCurrent_A"),
            "feeder_rate": self._node("gExtruderAI.FeederRateKgH"),
            "hopper_level": self._node("gExtruderAI.HopperLevelPct"),
        }

    async def _run_with_client(self, callback):
        client = Client(url=self.endpoint, timeout=self.timeout_s)
        try:
            await client.connect()
            self._connected = True
            return await callback(client)
        finally:
            self._connected = False
            try:
                await client.disconnect()
            except Exception:
                pass

    async def _read_values(self) -> Dict[str, object]:
        async def _reader(client: Client) -> Dict[str, object]:
            values: Dict[str, object] = {}
            for key, node_id in self._read_map().items():
                node = client.get_node(node_id)
                values[key] = await node.read_value()
            return values

        return await self._run_with_client(_reader)

    async def _write_value(self, node_id: str, value: object) -> None:
        async def _writer(client: Client) -> None:
            node = client.get_node(node_id)
            await node.write_value(value)

        await self._run_with_client(_writer)

    async def _write_values(self, values: Sequence[Tuple[str, object]]) -> None:
        async def _writer(client: Client) -> None:
            for node_id, value in values:
                node = client.get_node(node_id)
                await node.write_value(value)

        await self._run_with_client(_writer)

    async def _pulse_bool(self, node_id: str) -> None:
        async def _pulser(client: Client) -> None:
            node = client.get_node(node_id)
            await node.write_value(True)
            await asyncio.sleep(0.05)
            await node.write_value(False)

        await self._run_with_client(_pulser)

    async def _browse(self, node_id: str) -> List[Dict[str, str]]:
        async def _browser(client: Client) -> List[Dict[str, str]]:
            node = client.get_node(node_id)
            children = await node.get_children()
            items: List[Dict[str, str]] = []
            for child in children:
                browse_name = await child.read_browse_name()
                display_name = await child.read_display_name()
                node_class = await child.read_node_class()
                items.append(
                    {
                        "node_id": child.nodeid.to_string(),
                        "browse_name": str(browse_name),
                        "display_name": str(display_name.Text),
                        "node_class": str(node_class),
                    }
                )
            return items

        return await self._run_with_client(_browser)

    def _run(self, coroutine):
        return asyncio.run(coroutine)

    @staticmethod
    def _state_name(raw: object) -> str:
        if isinstance(raw, str):
            return raw
        return str(raw).split(".")[-1]

    @staticmethod
    def _severity_from_summary(any_alarm: bool, any_warning: bool) -> Optional[AlarmSeverity]:
        if any_alarm and not any_warning:
            return AlarmSeverity.FAULT
        if any_alarm and any_warning:
            return AlarmSeverity.CRITICAL
        if any_warning:
            return AlarmSeverity.WARNING
        return None

    @classmethod
    def _empty_snapshot(cls) -> Dict[str, object]:
        return {
            "state": "UNKNOWN",
            "scan_number": 0,
            "run_time_s": 0.0,
            "recipe": {"feed_rate_kg_h": 0.0, "screw_rpm": 0.0},
            "safety": {"state": "UNKNOWN"},
            "alarms": "No data",
            "heater": {
                "all_at_setpoint": False,
                "zones": [
                    {"zone": 1, "temperature_c": 0.0, "setpoint_c": 0.0, "heater_output_pct": 0.0, "at_setpoint": False},
                    {"zone": 2, "temperature_c": 0.0, "setpoint_c": 0.0, "heater_output_pct": 0.0, "at_setpoint": False},
                    {"zone": 3, "temperature_c": 0.0, "setpoint_c": 0.0, "heater_output_pct": 0.0, "at_setpoint": False},
                    {"zone": 4, "temperature_c": 0.0, "setpoint_c": 0.0, "heater_output_pct": 0.0, "at_setpoint": False},
                ],
            },
            "motor": {"actual_rpm": 0.0, "setpoint_rpm": 0.0, "current_a": 0.0, "torque_pct": 0.0},
            "feeder": {"actual_rate_kg_h": 0.0, "setpoint_kg_h": 0.0, "hopper_level_pct": 0.0},
            "die": {"temperature_c": 0.0, "setpoint_c": 0.0, "melt_pressure_bar": 0.0, "throughput_kg_h": 0.0},
            "active_alarms": [],
        }

    def _build_snapshot(self, values: Dict[str, object]) -> Dict[str, object]:
        state = self._state_name(values["state"])
        safety_state = self._state_name(values["safety_state"])
        heater_zones = [
            {
                "zone": 1,
                "temperature_c": float(values["zone1_temp"]),
                "setpoint_c": float(values["zone1_sp"]),
                "heater_output_pct": 0.0,
                "at_setpoint": abs(float(values["zone1_temp"]) - float(values["zone1_sp"])) <= 5.0,
            },
            {
                "zone": 2,
                "temperature_c": float(values["zone2_temp"]),
                "setpoint_c": float(values["zone2_sp"]),
                "heater_output_pct": 0.0,
                "at_setpoint": abs(float(values["zone2_temp"]) - float(values["zone2_sp"])) <= 5.0,
            },
            {
                "zone": 3,
                "temperature_c": float(values["zone3_temp"]),
                "setpoint_c": float(values["zone3_sp"]),
                "heater_output_pct": 0.0,
                "at_setpoint": abs(float(values["zone3_temp"]) - float(values["zone3_sp"])) <= 5.0,
            },
            {
                "zone": 4,
                "temperature_c": float(values["zone4_temp"]),
                "setpoint_c": float(values["zone4_sp"]),
                "heater_output_pct": 0.0,
                "at_setpoint": abs(float(values["zone4_temp"]) - float(values["zone4_sp"])) <= 5.0,
            },
        ]
        throughput = float(values["feeder_rate"]) * (
            float(values["motor_rpm"]) / 150.0 if float(values["motor_rpm"]) > 0 else 0.0
        )
        any_alarm = bool(values["alarm_any"])
        any_warning = bool(values["alarm_warning"])
        summary = "No active alarms"
        if any_alarm or any_warning:
            summary = (
                f"PLC AlarmWord {values['alarm_summary']}"
                f" | state={safety_state}"
            )
        severity = self._severity_from_summary(any_alarm, any_warning)
        self._cached_alarms = []
        if severity is not None:
            self._cached_alarms.append(
                Alarm(
                    code="PLC_ALARM_SUMMARY",
                    message=summary,
                    severity=severity,
                    timestamp=time.time(),
                )
            )

        snapshot = {
            "state": state,
            "scan_number": int(values["scan_number"]),
            "run_time_s": float(values["run_time_s"]),
            "recipe": {
                "feed_rate_kg_h": float(values["feed_rate_setpoint"]),
                "screw_rpm": float(values["screw_rpm_setpoint"]),
            },
            "safety": {"state": safety_state},
            "alarms": summary,
            "heater": {
                "all_at_setpoint": bool(values["heater_all_at_setpoint"]),
                "zones": heater_zones,
            },
            "motor": {
                "actual_rpm": float(values["motor_rpm"]),
                "setpoint_rpm": float(values["screw_rpm_setpoint"]),
                "current_a": float(values["motor_current"]),
                "torque_pct": 0.0,
            },
            "feeder": {
                "actual_rate_kg_h": float(values["feeder_rate"]),
                "setpoint_kg_h": float(values["feed_rate_setpoint"]),
                "hopper_level_pct": float(values["hopper_level"]),
            },
            "die": {
                "temperature_c": float(values["die_temp"]),
                "setpoint_c": float(values["die_sp"]),
                "melt_pressure_bar": float(values["pressure_bar"]),
                "throughput_kg_h": throughput,
            },
            "active_alarms": [
                {
                    "code": alarm.code,
                    "message": alarm.message,
                    "severity": alarm.severity.name,
                    "timestamp": alarm.timestamp,
                    "acknowledged": alarm.acknowledged,
                }
                for alarm in self._cached_alarms
            ],
            "active_recipe_name": str(values["recipe_name"]),
        }
        return snapshot

    def scan(self) -> None:
        try:
            values = self._run(self._read_values())
            self._last_snapshot = self._build_snapshot(values)
            self._last_error = ""
            self._last_poll_succeeded = True
        except Exception as exc:
            self._last_error = str(exc)
            self._last_poll_succeeded = False
            self._connected = False

    def _run_command(self, coroutine) -> bool:
        try:
            self._run(coroutine)
            self._last_error = ""
            return True
        except Exception as exc:
            close = getattr(coroutine, "close", None)
            if callable(close):
                close()
            self._last_error = str(exc)
            self._last_poll_succeeded = False
            self._connected = False
            return False

    def start(self) -> bool:
        return self._run_command(self._pulse_bool(self._node("gExtruderCmd.Start")))

    def stop(self) -> bool:
        return self._run_command(self._pulse_bool(self._node("gExtruderCmd.Stop")))

    def reset(self) -> bool:
        return self._run_command(self._pulse_bool(self._node("gExtruderCmd.Reset")))

    def emergency_stop(self) -> None:
        self._run_command(self._pulse_bool(self._node("gExtruderCmd.EmergencyStop")))

    def acknowledge_alarms(self) -> int:
        if self._run_command(self._pulse_bool(self._node("gExtruderCmd.Reset"))):
            return len(self._cached_alarms)
        return 0

    def set_recipe(
        self,
        feed_rate_kg_h: float,
        screw_rpm: float,
        zone_setpoints_c: Optional[List[float]] = None,
        die_setpoint_c: Optional[float] = None,
    ) -> None:
        zone_setpoints_c = zone_setpoints_c or []
        writes = [
            (self._node("gExtruderCmd.RecipeFeedRateKgH"), feed_rate_kg_h),
            (self._node("gExtruderCmd.RecipeScrewRpm"), screw_rpm),
        ]
        if len(zone_setpoints_c) > 0:
            writes.append((self._node("gExtruderCmd.Zone1Setpoint_C"), zone_setpoints_c[0]))
        if len(zone_setpoints_c) > 1:
            writes.append((self._node("gExtruderCmd.Zone2Setpoint_C"), zone_setpoints_c[1]))
        if len(zone_setpoints_c) > 2:
            writes.append((self._node("gExtruderCmd.Zone3Setpoint_C"), zone_setpoints_c[2]))
        if len(zone_setpoints_c) > 3:
            writes.append((self._node("gExtruderCmd.Zone4Setpoint_C"), zone_setpoints_c[3]))
        if die_setpoint_c is not None:
            writes.append((self._node("gExtruderCmd.DieSetpoint_C"), die_setpoint_c))

        self._run_command(self._write_values(writes))

    def status_snapshot(self) -> Dict[str, object]:
        if self._last_snapshot["state"] == "UNKNOWN":
            self.scan()
        return self._last_snapshot

    def active_alarms(self) -> List[Alarm]:
        return self._cached_alarms

    def close(self) -> None:
        self._connected = False

    def browse_nodes(self, node_id: Optional[str] = None) -> List[Dict[str, str]]:
        """Browse children below the configured node prefix or a supplied node."""
        target = node_id or self._node("gExtruderStatus")
        try:
            items = self._run(self._browse(target))
            self._last_error = ""
            return items
        except Exception as exc:
            self._last_error = str(exc)
            return []

    def diagnostics(self) -> Dict[str, object]:
        return {
            "plc_mode": self.mode_name,
            "connected": self._last_poll_succeeded,
            "endpoint": self.endpoint,
            "node_prefix": self.node_prefix,
            "last_error": self._last_error,
            "last_poll_succeeded": self._last_poll_succeeded,
        }


class ModbusPlcAdapter(BasePlcAdapter):
    """Modbus TCP adapter using a compact register/coil map."""

    mode_name = "modbus"

    START_COIL_OFFSET = 0
    STOP_COIL_OFFSET = 1
    RESET_COIL_OFFSET = 2
    EMERGENCY_STOP_COIL_OFFSET = 3
    ACK_ALARMS_COIL_OFFSET = 4

    DEFAULT_COMMAND_BASE_REGISTER = 2000
    DEFAULT_STATUS_BASE_REGISTER = 1000
    STATUS_REGISTER_COUNT = 25

    STATE_MAP = {
        0: "IDLE",
        1: "STARTUP",
        2: "RUNNING",
        3: "SHUTDOWN",
        4: "EMERGENCY_STOP",
        5: "UNAVAILABLE",
    }
    SAFETY_STATE_MAP = {
        0: "SAFE",
        1: "WARNING",
        2: "FAULT",
        3: "E_STOP",
        4: "UNKNOWN",
    }

    def __init__(
        self,
        endpoint: str,
        unit_id: int = 1,
        timeout_s: float = 2.0,
        command_coil_base: int = 0,
        status_base_register: int = DEFAULT_STATUS_BASE_REGISTER,
        command_base_register: int = DEFAULT_COMMAND_BASE_REGISTER,
    ) -> None:
        self.endpoint = endpoint
        self.unit_id = unit_id
        self.timeout_s = timeout_s
        self.command_coil_base = command_coil_base
        self.status_base_register = status_base_register
        self.command_base_register = command_base_register
        self._host, self._port = self._parse_endpoint(endpoint)
        self._connected = False
        self._cached_alarms: List[Alarm] = []
        self._last_error = (
            "The pymodbus package is required for Modbus mode. "
            "Install dependencies from requirements.txt first."
            if ModbusTcpClient is None
            else "Awaiting Modbus scan"
        )
        self._last_poll_succeeded = False
        self._last_snapshot = self._empty_snapshot()

    def _coil_address(self, offset: int) -> int:
        return self.command_coil_base + offset

    @classmethod
    def _parse_endpoint(cls, endpoint: str) -> Tuple[str, int]:
        candidate = endpoint.strip()
        parsed = urlparse(candidate if "://" in candidate else f"tcp://{candidate}")
        if not parsed.hostname:
            raise ValueError(
                "Invalid EXTRUDER_MODBUS_ENDPOINT. Use host:port or tcp://host:port."
            )
        return parsed.hostname, parsed.port or 502

    @classmethod
    def _empty_snapshot(cls) -> Dict[str, object]:
        return {
            "state": "UNAVAILABLE",
            "scan_number": 0,
            "run_time_s": 0.0,
            "recipe": {"feed_rate_kg_h": 0.0, "screw_rpm": 0.0},
            "safety": {"state": "UNKNOWN"},
            "alarms": "No data from Modbus PLC",
            "heater": {
                "all_at_setpoint": False,
                "zones": [
                    {
                        "zone": zone,
                        "temperature_c": 0.0,
                        "setpoint_c": 0.0,
                        "heater_output_pct": 0.0,
                        "at_setpoint": False,
                    }
                    for zone in range(1, 5)
                ],
            },
            "motor": {
                "actual_rpm": 0.0,
                "setpoint_rpm": 0.0,
                "current_a": 0.0,
                "torque_pct": 0.0,
            },
            "feeder": {
                "actual_rate_kg_h": 0.0,
                "setpoint_kg_h": 0.0,
                "hopper_level_pct": 0.0,
            },
            "die": {
                "temperature_c": 0.0,
                "setpoint_c": 0.0,
                "melt_pressure_bar": 0.0,
                "throughput_kg_h": 0.0,
            },
            "active_alarms": [],
        }

    @staticmethod
    def _decode_scaled(value: int, scale: float = 10.0) -> float:
        if value >= 0x8000:
            value -= 0x10000
        return value / scale

    @staticmethod
    def _decode_u32(high_word: int, low_word: int) -> int:
        return ((high_word & 0xFFFF) << 16) | (low_word & 0xFFFF)

    @staticmethod
    def _encode_scaled(value: float, scale: float = 10.0) -> int:
        encoded = int(round(value * scale))
        return encoded & 0xFFFF

    @classmethod
    def _state_name(cls, raw: int) -> str:
        return cls.STATE_MAP.get(int(raw), "UNKNOWN")

    @classmethod
    def _safety_state_name(cls, raw: int) -> str:
        return cls.SAFETY_STATE_MAP.get(int(raw), "UNKNOWN")

    @staticmethod
    def _severity_from_summary(any_alarm: bool, any_warning: bool) -> Optional[AlarmSeverity]:
        if any_alarm and not any_warning:
            return AlarmSeverity.FAULT
        if any_alarm and any_warning:
            return AlarmSeverity.CRITICAL
        if any_warning:
            return AlarmSeverity.WARNING
        return None

    def _run_with_client(self, callback):
        if ModbusTcpClient is None:
            raise RuntimeError(
                "The pymodbus package is required for Modbus mode. "
                "Install dependencies from requirements.txt first."
            )
        client = ModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=self.timeout_s,
        )
        connected = False
        try:
            result = client.connect()
            connected = bool(result)
            if result is None:
                connected = bool(getattr(client, "connected", False))
        except Exception:
            connected = False
        if not connected:
            close = getattr(client, "close", None)
            if callable(close):
                close()
            raise RuntimeError(
                f"Unable to connect to Modbus PLC at {self._host}:{self._port}"
            )
        self._connected = True
        try:
            return callback(client)
        finally:
            self._connected = False
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def _call_with_unit(self, method, *args):
        for keyword in ("slave", "unit"):
            try:
                return method(*args, **{keyword: self.unit_id})
            except TypeError:
                continue
        return method(*args)

    @staticmethod
    def _ensure_response_ok(response) -> None:
        if response is None:
            raise RuntimeError("No response returned from Modbus PLC")
        is_error = getattr(response, "isError", None)
        if callable(is_error) and response.isError():
            raise RuntimeError(str(response))

    def _read_holding_registers(self, client, address: int, count: int):
        response = self._call_with_unit(client.read_holding_registers, address, count)
        self._ensure_response_ok(response)
        registers = getattr(response, "registers", None)
        if registers is None or len(registers) < count:
            raise RuntimeError(
                f"Modbus PLC returned {0 if registers is None else len(registers)} "
                f"holding registers, expected {count}"
            )
        return registers

    def _write_registers(self, client, address: int, values: List[int]) -> None:
        response = self._call_with_unit(client.write_registers, address, values)
        self._ensure_response_ok(response)

    def _write_coil(self, client, address: int, value: bool) -> None:
        response = self._call_with_unit(client.write_coil, address, value)
        self._ensure_response_ok(response)

    def _pulse_coil(self, client, address: int) -> None:
        self._write_coil(client, address, True)
        time.sleep(0.05)
        self._write_coil(client, address, False)

    def _build_snapshot(self, registers: Sequence[int]) -> Dict[str, object]:
        flags = int(registers[7])
        any_alarm = bool(flags & 0b0001)
        any_warning = bool(flags & 0b0010)
        heater_all_at_setpoint = bool(flags & 0b0100)
        die_at_setpoint = bool(flags & 0b1000)
        safety_state = self._safety_state_name(registers[5])
        summary = "No active alarms"
        if any_alarm or any_warning:
            summary = (
                f"Modbus AlarmWord {int(registers[6])}"
                f" | state={safety_state}"
            )

        severity = self._severity_from_summary(any_alarm, any_warning)
        self._cached_alarms = []
        if severity is not None:
            self._cached_alarms.append(
                Alarm(
                    code="MODBUS_ALARM_SUMMARY",
                    message=summary,
                    severity=severity,
                    timestamp=time.time(),
                )
            )

        zone_temps = [self._decode_scaled(registers[index]) for index in range(15, 19)]
        zone_setpoints = [self._decode_scaled(registers[index]) for index in range(10, 14)]
        feeder_rate = self._decode_scaled(registers[23])
        motor_rpm = self._decode_scaled(registers[21])
        throughput = feeder_rate * (motor_rpm / 150.0 if motor_rpm > 0 else 0.0)

        snapshot = {
            "state": self._state_name(registers[0]),
            "scan_number": self._decode_u32(registers[1], registers[2]),
            "run_time_s": self._decode_u32(registers[3], registers[4]) / 10.0,
            "recipe": {
                "feed_rate_kg_h": self._decode_scaled(registers[8]),
                "screw_rpm": self._decode_scaled(registers[9]),
            },
            "safety": {"state": safety_state},
            "alarms": summary,
            "heater": {
                "all_at_setpoint": heater_all_at_setpoint,
                "zones": [
                    {
                        "zone": idx + 1,
                        "temperature_c": zone_temps[idx],
                        "setpoint_c": zone_setpoints[idx],
                        "heater_output_pct": 0.0,
                        "at_setpoint": abs(zone_temps[idx] - zone_setpoints[idx]) <= 5.0,
                    }
                    for idx in range(4)
                ],
            },
            "motor": {
                "actual_rpm": motor_rpm,
                "setpoint_rpm": self._decode_scaled(registers[9]),
                "current_a": self._decode_scaled(registers[22]),
                "torque_pct": 0.0,
            },
            "feeder": {
                "actual_rate_kg_h": feeder_rate,
                "setpoint_kg_h": self._decode_scaled(registers[8]),
                "hopper_level_pct": self._decode_scaled(registers[24]),
            },
            "die": {
                "temperature_c": self._decode_scaled(registers[19]),
                "setpoint_c": self._decode_scaled(registers[14]),
                "melt_pressure_bar": self._decode_scaled(registers[20]),
                "throughput_kg_h": throughput,
                "at_setpoint": die_at_setpoint,
            },
            "active_alarms": [
                {
                    "code": alarm.code,
                    "message": alarm.message,
                    "severity": alarm.severity.name,
                    "timestamp": alarm.timestamp,
                    "acknowledged": alarm.acknowledged,
                }
                for alarm in self._cached_alarms
            ],
        }
        return snapshot

    def _run_command(self, callback) -> bool:
        try:
            self._run_with_client(callback)
            self._last_error = ""
            self._last_poll_succeeded = True
            return True
        except Exception as exc:
            self._last_error = str(exc)
            self._last_poll_succeeded = False
            self._connected = False
            return False

    def _apply_recipe_snapshot(
        self,
        feed_rate_kg_h: float,
        screw_rpm: float,
        zone_setpoints_c: Sequence[float],
        die_setpoint_c: Optional[float],
    ) -> None:
        self._last_snapshot["recipe"] = {
            "feed_rate_kg_h": float(feed_rate_kg_h),
            "screw_rpm": float(screw_rpm),
        }
        self._last_snapshot["feeder"]["setpoint_kg_h"] = float(feed_rate_kg_h)
        self._last_snapshot["motor"]["setpoint_rpm"] = float(screw_rpm)
        for idx, temp in enumerate(zone_setpoints_c[:4]):
            self._last_snapshot["heater"]["zones"][idx]["setpoint_c"] = float(temp)
        if die_setpoint_c is not None:
            self._last_snapshot["die"]["setpoint_c"] = float(die_setpoint_c)

    def scan(self) -> None:
        try:
            registers = self._run_with_client(
                lambda client: self._read_holding_registers(
                    client,
                    self.status_base_register,
                    self.STATUS_REGISTER_COUNT,
                )
            )
            self._last_snapshot = self._build_snapshot(registers)
            self._last_error = ""
            self._last_poll_succeeded = True
        except Exception as exc:
            self._last_error = str(exc)
            self._last_poll_succeeded = False
            self._connected = False

    def start(self) -> bool:
        return self._run_command(
            lambda client: self._pulse_coil(client, self._coil_address(self.START_COIL_OFFSET))
        )

    def stop(self) -> bool:
        return self._run_command(
            lambda client: self._pulse_coil(client, self._coil_address(self.STOP_COIL_OFFSET))
        )

    def reset(self) -> bool:
        return self._run_command(
            lambda client: self._pulse_coil(client, self._coil_address(self.RESET_COIL_OFFSET))
        )

    def emergency_stop(self) -> None:
        self._run_command(
            lambda client: self._pulse_coil(client, self._coil_address(self.EMERGENCY_STOP_COIL_OFFSET))
        )

    def acknowledge_alarms(self) -> int:
        if self._run_command(
            lambda client: self._pulse_coil(client, self._coil_address(self.ACK_ALARMS_COIL_OFFSET))
        ):
            return len(self._cached_alarms)
        return 0

    def set_recipe(
        self,
        feed_rate_kg_h: float,
        screw_rpm: float,
        zone_setpoints_c: Optional[List[float]] = None,
        die_setpoint_c: Optional[float] = None,
    ) -> None:
        zone_setpoints_c = zone_setpoints_c or []
        writes = [
            self._encode_scaled(feed_rate_kg_h),
            self._encode_scaled(screw_rpm),
            self._encode_scaled(zone_setpoints_c[0]) if len(zone_setpoints_c) > 0 else 0,
            self._encode_scaled(zone_setpoints_c[1]) if len(zone_setpoints_c) > 1 else 0,
            self._encode_scaled(zone_setpoints_c[2]) if len(zone_setpoints_c) > 2 else 0,
            self._encode_scaled(zone_setpoints_c[3]) if len(zone_setpoints_c) > 3 else 0,
            self._encode_scaled(die_setpoint_c) if die_setpoint_c is not None else 0,
        ]
        self._apply_recipe_snapshot(
            feed_rate_kg_h=feed_rate_kg_h,
            screw_rpm=screw_rpm,
            zone_setpoints_c=zone_setpoints_c,
            die_setpoint_c=die_setpoint_c,
        )
        self._run_command(
            lambda client: self._write_registers(
                client,
                self.command_base_register,
                writes,
            )
        )

    def status_snapshot(self) -> Dict[str, object]:
        return self._last_snapshot

    def active_alarms(self) -> List[Alarm]:
        return self._cached_alarms

    def diagnostics(self) -> Dict[str, object]:
        return {
            "plc_mode": self.mode_name,
            "connected": self._last_poll_succeeded,
            "endpoint": self.endpoint,
            "node_prefix": "",
            "last_error": self._last_error,
            "last_poll_succeeded": self._last_poll_succeeded,
        }
