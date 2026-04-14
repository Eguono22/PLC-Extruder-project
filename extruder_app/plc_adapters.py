"""PLC communication adapters for the extruder application."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from plc_extruder.controller import ExtruderController
from plc_extruder.utils.alarms import Alarm


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


class OpcUaPlcAdapter(BasePlcAdapter):
    """Placeholder for a future OPC UA-backed PLC adapter."""

    mode_name = "opcua"

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def _unimplemented(self) -> None:
        raise NotImplementedError(
            "OPC UA integration is scaffolded but not yet implemented in this repo."
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


class ModbusPlcAdapter(OpcUaPlcAdapter):
    """Placeholder for a future Modbus-backed PLC adapter."""

    mode_name = "modbus"
