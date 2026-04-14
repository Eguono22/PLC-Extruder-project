"""PLC communication adapters for the extruder application."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Tuple

from plc_extruder.controller import ExtruderController
from plc_extruder.utils.alarms import Alarm, AlarmSeverity

try:
    from asyncua import Client
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    Client = None


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

    def start(self) -> bool:
        self._run(self._pulse_bool(self._node("gExtruderCmd.Start")))
        return True

    def stop(self) -> bool:
        self._run(self._pulse_bool(self._node("gExtruderCmd.Stop")))
        return True

    def reset(self) -> bool:
        self._run(self._pulse_bool(self._node("gExtruderCmd.Reset")))
        return True

    def emergency_stop(self) -> None:
        self._run(self._pulse_bool(self._node("gExtruderCmd.EmergencyStop")))

    def acknowledge_alarms(self) -> int:
        self._run(self._pulse_bool(self._node("gExtruderCmd.Reset")))
        return len(self._cached_alarms)

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

        self._run(self._write_values(writes))

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
    """Placeholder for a future Modbus-backed PLC adapter."""

    mode_name = "modbus"

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def _unimplemented(self) -> None:
        raise NotImplementedError(
            "Modbus integration is scaffolded but not yet implemented in this repo."
        )

    def scan(self) -> None:
        self._unimplemented()

    def start(self) -> bool:
        self._unimplemented()
        return False

    def stop(self) -> bool:
        self._unimplemented()
        return False

    def reset(self) -> bool:
        self._unimplemented()
        return False

    def emergency_stop(self) -> None:
        self._unimplemented()

    def acknowledge_alarms(self) -> int:
        self._unimplemented()
        return 0

    def set_recipe(
        self,
        feed_rate_kg_h: float,
        screw_rpm: float,
        zone_setpoints_c: Optional[List[float]] = None,
        die_setpoint_c: Optional[float] = None,
    ) -> None:
        self._unimplemented()

    def status_snapshot(self) -> Dict[str, object]:
        self._unimplemented()
        return {}

    def active_alarms(self) -> List[Alarm]:
        self._unimplemented()
        return []

    def diagnostics(self) -> Dict[str, object]:
        return {
            "plc_mode": self.mode_name,
            "connected": False,
            "endpoint": self.endpoint,
            "node_prefix": "",
            "last_error": "Modbus adapter not implemented",
            "last_poll_succeeded": False,
        }
