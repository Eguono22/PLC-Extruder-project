"""
Safety system – emergency stop, interlocks, and watchdog.

The safety system is the highest-priority layer of the control hierarchy.
It continuously evaluates hardwired interlock conditions and can assert an
**Emergency Stop (E-Stop)** that immediately de-energises all drives and
heaters regardless of the normal PLC scan outputs.

Interlock conditions checked every scan cycle
----------------------------------------------
1. Any barrel zone temperature ≥ ``MAX_BARREL_TEMP``
2. Die pressure ≥ ``DIE_MAX_PRESSURE``
3. Motor over-current (via alarm state)
4. E-Stop button pressed (physical or software)
5. Barrel temperature sensor loss-of-signal (not simulated here but
   modelled as a flag that can be set externally)

The safety system itself is stateless with respect to process data – it
reads component state through the controller interface passed in on each
``evaluate`` call.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from plc_extruder.utils.alarms import AlarmManager, AlarmSeverity

if TYPE_CHECKING:
    # Avoid circular import; only used for type hints
    from plc_extruder.components.heater import BarrelHeater
    from plc_extruder.components.motor import ExtrusionMotor
    from plc_extruder.components.die import DieZone
    from plc_extruder.components.feeder import MaterialFeeder

import config


class SafetyState(Enum):
    """Safety system states."""
    SAFE = auto()
    WARNING = auto()
    E_STOP = auto()


class SafetySystem:
    """Hardwired safety interlock evaluator.

    This class is intentionally **not** responsible for executing the
    stop actions – it only signals when a stop is required.  The
    :class:`~plc_extruder.controller.ExtruderController` acts on the
    safety state every scan cycle.

    Args:
        alarm_manager: Shared :class:`AlarmManager` instance.
    """

    # Alarm codes raised by the safety system itself
    _ALM_ESTOP_HW = "SAFETY_ESTOP_HW"
    _ALM_ESTOP_SW = "SAFETY_ESTOP_SW"
    _ALM_INTERLOCK_TEMP = "SAFETY_INTERLOCK_TEMP"
    _ALM_INTERLOCK_PRESSURE = "SAFETY_INTERLOCK_PRESSURE"
    _ALM_INTERLOCK_CURRENT = "SAFETY_INTERLOCK_CURRENT"
    _ALM_WATCHDOG = "SAFETY_WATCHDOG"

    def __init__(self, alarm_manager: AlarmManager) -> None:
        self._alarms = alarm_manager
        self._state = SafetyState.SAFE
        self._estop_hw: bool = False   # Hardware E-Stop button
        self._estop_sw: bool = False   # Software-initiated E-Stop
        self._scan_count: int = 0
        self._watchdog_limit: int = 100  # scans without reset → fault

    # ------------------------------------------------------------------
    # E-Stop triggers
    # ------------------------------------------------------------------

    def trigger_estop_hardware(self) -> None:
        """Assert the hardware emergency-stop signal."""
        self._estop_hw = True

    def reset_estop_hardware(self) -> None:
        """De-assert hardware E-Stop (operator key-switch reset)."""
        self._estop_hw = False
        self._alarms.clear_alarm(self._ALM_ESTOP_HW)

    def trigger_estop_software(self) -> None:
        """Assert a software-initiated emergency stop."""
        self._estop_sw = True

    def reset_estop_software(self) -> None:
        """Clear the software E-Stop."""
        self._estop_sw = False
        self._alarms.clear_alarm(self._ALM_ESTOP_SW)

    def reset_all(self) -> None:
        """Reset both E-Stop signals and transition back to SAFE.

        The caller must ensure that the underlying fault condition has
        been resolved before calling this method.
        """
        self._estop_hw = False
        self._estop_sw = False
        self._state = SafetyState.SAFE
        self._scan_count = 0
        for code in (
            self._ALM_ESTOP_HW,
            self._ALM_ESTOP_SW,
            self._ALM_INTERLOCK_TEMP,
            self._ALM_INTERLOCK_PRESSURE,
            self._ALM_INTERLOCK_CURRENT,
            self._ALM_WATCHDOG,
        ):
            self._alarms.clear_alarm(code)

    # ------------------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------------------

    def pet_watchdog(self) -> None:
        """Reset the watchdog counter (must be called every scan cycle)."""
        self._scan_count = 0

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        heater: "BarrelHeater",
        motor: "ExtrusionMotor",
        die: "DieZone",
        feeder: "MaterialFeeder",
    ) -> SafetyState:
        """Evaluate all interlock conditions and update safety state.

        This method is idempotent – repeated calls with the same inputs
        return the same result.

        Args:
            heater: Barrel heater assembly reference.
            motor: Extrusion motor reference.
            die: Die zone reference.
            feeder: Material feeder reference.

        Returns:
            Current :class:`SafetyState`.
        """
        e_stop_required = False

        # 1. Hardware E-Stop button
        if self._estop_hw:
            self._alarms.raise_alarm(
                self._ALM_ESTOP_HW,
                "Hardware emergency stop activated",
                AlarmSeverity.CRITICAL,
            )
            e_stop_required = True

        # 2. Software E-Stop
        if self._estop_sw:
            self._alarms.raise_alarm(
                self._ALM_ESTOP_SW,
                "Software emergency stop activated",
                AlarmSeverity.CRITICAL,
            )
            e_stop_required = True

        # 3. Over-temperature interlock (any barrel zone)
        for zone in heater.zones:
            if zone.temperature >= config.MAX_BARREL_TEMP:
                self._alarms.raise_alarm(
                    self._ALM_INTERLOCK_TEMP,
                    f"Interlock: Zone {zone.zone_index + 1} temperature "
                    f"{zone.temperature:.1f} °C ≥ {config.MAX_BARREL_TEMP} °C",
                    AlarmSeverity.CRITICAL,
                )
                e_stop_required = True
                break
        else:
            if self._alarms.has_active(self._ALM_INTERLOCK_TEMP):
                self._alarms.clear_alarm(self._ALM_INTERLOCK_TEMP)

        # 4. Die over-pressure interlock
        if die.melt_pressure_bar >= config.DIE_MAX_PRESSURE:
            self._alarms.raise_alarm(
                self._ALM_INTERLOCK_PRESSURE,
                f"Interlock: Die pressure {die.melt_pressure_bar:.1f} bar "
                f"≥ {config.DIE_MAX_PRESSURE} bar",
                AlarmSeverity.CRITICAL,
            )
            e_stop_required = True
        else:
            if self._alarms.has_active(self._ALM_INTERLOCK_PRESSURE):
                self._alarms.clear_alarm(self._ALM_INTERLOCK_PRESSURE)

        # 5. Motor over-current (motor reports its own fault)
        if motor.has_fault:
            self._alarms.raise_alarm(
                self._ALM_INTERLOCK_CURRENT,
                f"Interlock: Motor fault (I={motor.current_a:.1f} A)",
                AlarmSeverity.CRITICAL,
            )
            e_stop_required = True
        else:
            if self._alarms.has_active(self._ALM_INTERLOCK_CURRENT):
                self._alarms.clear_alarm(self._ALM_INTERLOCK_CURRENT)

        # 6. Watchdog
        self._scan_count += 1
        if self._scan_count > self._watchdog_limit:
            self._alarms.raise_alarm(
                self._ALM_WATCHDOG,
                "Watchdog timeout – scan cycle stalled",
                AlarmSeverity.CRITICAL,
            )
            e_stop_required = True

        # Determine overall safety state
        if e_stop_required:
            self._state = SafetyState.E_STOP
        elif self._alarms.highest_severity() == AlarmSeverity.WARNING:
            self._state = SafetyState.WARNING
        else:
            self._state = SafetyState.SAFE

        return self._state

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> SafetyState:
        """Current safety system state."""
        return self._state

    @property
    def is_estop_active(self) -> bool:
        """True if any E-Stop condition is active."""
        return self._state == SafetyState.E_STOP

    @property
    def estop_hw(self) -> bool:
        """True if the hardware E-Stop button is depressed."""
        return self._estop_hw

    @property
    def estop_sw(self) -> bool:
        """True if a software E-Stop has been commanded."""
        return self._estop_sw

    def status_dict(self) -> dict:
        """Return safety system snapshot."""
        return {
            "state": self._state.name,
            "estop_hw": self._estop_hw,
            "estop_sw": self._estop_sw,
            "scan_count": self._scan_count,
            "is_estop_active": self.is_estop_active,
        }

    def __repr__(self) -> str:
        return (
            f"SafetySystem(state={self._state.name}, "
            f"estop_hw={self._estop_hw}, estop_sw={self._estop_sw})"
        )
