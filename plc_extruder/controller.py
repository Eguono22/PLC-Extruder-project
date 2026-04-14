"""
Main PLC extruder controller – state machine and scan-cycle orchestration.

The :class:`ExtruderController` is the top-level object that owns every
component and drives the complete extrusion process through the following
states:

.. code-block:: text

    IDLE ──start()──► STARTUP ──temps ready──► RUNNING
                                                   │
                                              stop()│
                                                   ▼
                                              SHUTDOWN ──complete──► IDLE
    Any state ──E-Stop / safety fault──► EMERGENCY_STOP
    EMERGENCY_STOP ──reset()──► IDLE

Usage example::

    ctrl = ExtruderController()
    ctrl.set_recipe(feed_rate=50.0, screw_rpm=80.0)
    ctrl.start()
    for _ in range(10_000):       # simulate 1000 s at 0.1 s scan cycle
        ctrl.scan()
    ctrl.stop()
"""

from __future__ import annotations

import time
from enum import Enum, auto
from typing import Optional

from plc_extruder.components.feeder import MaterialFeeder
from plc_extruder.components.heater import BarrelHeater
from plc_extruder.components.motor import ExtrusionMotor
from plc_extruder.components.die import DieZone
from plc_extruder.components.safety import SafetySystem, SafetyState
from plc_extruder.utils.alarms import AlarmManager, AlarmSeverity
import config


class ControllerState(Enum):
    """High-level extruder operating states."""
    IDLE = auto()
    STARTUP = auto()
    RUNNING = auto()
    SHUTDOWN = auto()
    EMERGENCY_STOP = auto()


class ExtruderController:
    """Top-level PLC controller for the industrial extruder platform.

    All physical sub-systems are owned by this class and are updated on
    every call to :meth:`scan`.

    Args:
        scan_cycle_s: PLC scan cycle time in seconds (default 100 ms).
        initial_hopper_pct: Starting hopper fill level (0–100 %).
    """

    def __init__(
        self,
        scan_cycle_s: float = config.SCAN_CYCLE_S,
        initial_hopper_pct: float = 100.0,
    ) -> None:
        self._dt = scan_cycle_s
        self._state = ControllerState.IDLE
        self._scan_number: int = 0
        self._run_time_s: float = 0.0

        # Shared alarm manager
        self.alarms = AlarmManager()

        # Sub-systems
        self.feeder = MaterialFeeder(
            alarm_manager=self.alarms,
            initial_level_pct=initial_hopper_pct,
        )
        self.heater = BarrelHeater(alarm_manager=self.alarms)
        self.motor = ExtrusionMotor(alarm_manager=self.alarms)
        self.die = DieZone(alarm_manager=self.alarms)
        self.safety = SafetySystem(alarm_manager=self.alarms)

        # Recipe / process setpoints
        self._recipe_feed_rate: float = config.FEEDER_MIN_RATE
        self._recipe_screw_rpm: float = config.MOTOR_MIN_RPM

    # ------------------------------------------------------------------
    # Operator commands
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Initiate the startup sequence.

        Returns:
            True if the transition to STARTUP was accepted, False if the
            controller is not in IDLE state.
        """
        if self._state != ControllerState.IDLE:
            return False
        self._transition_to(ControllerState.STARTUP)
        return True

    def stop(self) -> bool:
        """Initiate a controlled shutdown.

        Returns:
            True if the transition to SHUTDOWN was accepted.
        """
        if self._state not in (ControllerState.RUNNING, ControllerState.STARTUP):
            return False
        self._transition_to(ControllerState.SHUTDOWN)
        return True

    def emergency_stop(self) -> None:
        """Immediately assert an E-Stop (software trigger)."""
        self.safety.trigger_estop_software()
        self._transition_to(ControllerState.EMERGENCY_STOP)

    def reset(self) -> bool:
        """Reset from EMERGENCY_STOP or IDLE back to IDLE.

        Returns:
            True if reset was accepted.
        """
        if self._state not in (ControllerState.EMERGENCY_STOP, ControllerState.IDLE):
            return False
        self.safety.reset_all()
        self.motor.reset_fault()
        self.feeder.reset_fault()
        self.alarms.reset()
        self._run_time_s = 0.0
        self._transition_to(ControllerState.IDLE)
        return True

    def set_recipe(
        self,
        feed_rate: Optional[float] = None,
        screw_rpm: Optional[float] = None,
    ) -> None:
        """Update process recipe setpoints.

        Values are applied to the hardware immediately if the controller
        is RUNNING; otherwise they take effect at the next startup.

        Args:
            feed_rate: Desired feed rate (kg/h).
            screw_rpm: Desired screw speed (RPM).
        """
        if feed_rate is not None:
            self._recipe_feed_rate = max(
                config.FEEDER_MIN_RATE, min(config.FEEDER_MAX_RATE, feed_rate)
            )
        if screw_rpm is not None:
            self._recipe_screw_rpm = max(
                config.MOTOR_MIN_RPM, min(config.MOTOR_MAX_RPM, screw_rpm)
            )
        if self._state == ControllerState.RUNNING:
            self.feeder.set_rate(self._recipe_feed_rate)
            self.motor.set_speed(self._recipe_screw_rpm)

    def acknowledge_alarms(self) -> int:
        """Acknowledge all active alarms.

        Returns:
            Number of alarms acknowledged.
        """
        return self.alarms.acknowledge_all()

    # ------------------------------------------------------------------
    # Main scan cycle
    # ------------------------------------------------------------------

    def scan(self) -> ControllerState:
        """Execute one PLC scan cycle.

        Must be called at the configured scan rate (``scan_cycle_s``).

        Returns:
            The current :class:`ControllerState` after the scan.
        """
        self._scan_number += 1
        self.safety.pet_watchdog()

        # Evaluate safety interlocks (highest priority)
        safety_state = self.safety.evaluate(
            self.heater, self.motor, self.die, self.feeder
        )

        if safety_state == SafetyState.E_STOP and self._state not in (
            ControllerState.EMERGENCY_STOP,
            ControllerState.IDLE,
        ):
            self._transition_to(ControllerState.EMERGENCY_STOP)

        # State-specific logic
        if self._state == ControllerState.IDLE:
            self._scan_idle()
        elif self._state == ControllerState.STARTUP:
            self._scan_startup()
        elif self._state == ControllerState.RUNNING:
            self._scan_running()
        elif self._state == ControllerState.SHUTDOWN:
            self._scan_shutdown()
        elif self._state == ControllerState.EMERGENCY_STOP:
            self._scan_emergency_stop()

        # Update run-time counter
        if self._state == ControllerState.RUNNING:
            self._run_time_s += self._dt

        return self._state

    # ------------------------------------------------------------------
    # State entry actions
    # ------------------------------------------------------------------

    def _transition_to(self, new_state: ControllerState) -> None:
        """Execute state entry actions on transition."""
        self._state = new_state

        if new_state == ControllerState.STARTUP:
            self.heater.enable_all()
            self.die.enable()

        elif new_state == ControllerState.RUNNING:
            self.feeder.set_rate(self._recipe_feed_rate)
            self.motor.set_speed(self._recipe_screw_rpm)
            self.feeder.start()
            self.motor.start()

        elif new_state == ControllerState.SHUTDOWN:
            # Stop feeding and ramp motor down
            self.feeder.stop()
            self.motor.stop()
            self.alarms.raise_alarm(
                "SYSTEM_SHUTDOWN",
                "Controlled shutdown initiated",
                AlarmSeverity.INFO,
            )

        elif new_state == ControllerState.EMERGENCY_STOP:
            self.feeder.stop()
            self.motor.stop()
            self.heater.disable_all()
            self.die.disable()
            self.alarms.raise_alarm(
                "SYSTEM_ESTOP",
                "EMERGENCY STOP – all outputs de-energised",
                AlarmSeverity.CRITICAL,
            )

        elif new_state == ControllerState.IDLE:
            self.feeder.stop()
            self.motor.stop()
            self.heater.disable_all()
            self.die.disable()

    # ------------------------------------------------------------------
    # Per-state scan logic
    # ------------------------------------------------------------------

    def _scan_idle(self) -> None:
        """IDLE: Keep all outputs off, update temperatures (passive cool)."""
        self.heater.update(self._dt)
        self.die.update(self._dt)
        self.feeder.update(self._dt)
        self.motor.update(self._dt)

    def _scan_startup(self) -> None:
        """STARTUP: Heat all zones to setpoint; motor/feeder off."""
        self.heater.update(self._dt)
        self.die.update(self._dt)
        self.feeder.update(self._dt)
        self.motor.update(self._dt)

        if self.heater.all_at_setpoint and self.die.at_setpoint:
            self._transition_to(ControllerState.RUNNING)

    def _scan_running(self) -> None:
        """RUNNING: Full production – all systems active."""
        self.heater.update(self._dt)
        self.die.update(
            self._dt,
            screw_rpm=self.motor.actual_rpm,
            feed_rate_kg_h=self.feeder.actual_rate,
        )
        self.feeder.update(self._dt)
        self.motor.update(self._dt, melt_pressure_bar=self.die.melt_pressure_bar)

    def _scan_shutdown(self) -> None:
        """SHUTDOWN: Motor decelerating, heaters maintained, feeder stopped."""
        self.heater.update(self._dt)
        self.die.update(
            self._dt,
            screw_rpm=self.motor.actual_rpm,
            feed_rate_kg_h=0.0,
        )
        self.feeder.update(self._dt)
        self.motor.update(self._dt, melt_pressure_bar=self.die.melt_pressure_bar)

        # Complete shutdown once motor has stopped
        if self.motor.actual_rpm < 0.5:
            self.heater.disable_all()
            self.die.disable()
            self._transition_to(ControllerState.IDLE)
            self.alarms.clear_alarm("SYSTEM_SHUTDOWN")

    def _scan_emergency_stop(self) -> None:
        """EMERGENCY_STOP: All outputs off, passive cool-down only."""
        self.heater.update(self._dt)
        self.die.update(self._dt)
        self.feeder.update(self._dt)
        self.motor.update(self._dt)

    # ------------------------------------------------------------------
    # Status / reporting
    # ------------------------------------------------------------------

    @property
    def state(self) -> ControllerState:
        """Current controller state."""
        return self._state

    @property
    def scan_number(self) -> int:
        """Total scan cycles executed."""
        return self._scan_number

    @property
    def run_time_s(self) -> float:
        """Accumulated production run time (seconds)."""
        return self._run_time_s

    def status_dict(self) -> dict:
        """Return a comprehensive system snapshot for logging or HMI."""
        return {
            "state": self._state.name,
            "scan_number": self._scan_number,
            "run_time_s": round(self._run_time_s, 1),
            "recipe": {
                "feed_rate_kg_h": self._recipe_feed_rate,
                "screw_rpm": self._recipe_screw_rpm,
            },
            "safety": self.safety.status_dict(),
            "alarms": self.alarms.summary(),
            "heater": self.heater.status_dict(),
            "motor": self.motor.status_dict(),
            "feeder": self.feeder.status_dict(),
            "die": self.die.status_dict(),
        }

    def format_status(self) -> str:
        """Return a human-readable multi-line status string for the CLI."""
        s = self.status_dict()
        lines = [
            "=" * 60,
            f"  EXTRUDER CONTROL SYSTEM  –  State: {s['state']}",
            f"  Scan #{s['scan_number']:>6}  |  Run time: {s['run_time_s']:.1f} s",
            "=" * 60,
            f"  Recipe : feed={s['recipe']['feed_rate_kg_h']:.1f} kg/h, "
            f"RPM={s['recipe']['screw_rpm']:.0f}",
            f"  Safety : {s['safety']['state']}",
            f"  Alarms : {s['alarms']}",
            "-" * 60,
            "  BARREL ZONES (°C):",
        ]
        for z in s["heater"]["zones"]:
            lines.append(
                f"    Zone {z['zone']}: {z['temperature_c']:6.1f} / {z['setpoint_c']:.0f} °C  "
                f"Heater {z['heater_output_pct']:5.1f}%  "
                f"{'✓' if z['at_setpoint'] else '…'}"
            )
        die = s["die"]
        lines += [
            f"  DIE   : {die['temperature_c']:6.1f} / {die['setpoint_c']:.0f} °C  "
            f"P={die['melt_pressure_bar']:.1f} bar  "
            f"Q={die['throughput_kg_h']:.1f} kg/h",
            f"  MOTOR : {s['motor']['actual_rpm']:6.1f} / {s['motor']['setpoint_rpm']:.0f} RPM  "
            f"I={s['motor']['current_a']:.1f} A  T={s['motor']['torque_pct']:.0f}%",
            f"  FEEDER: {s['feeder']['actual_rate_kg_h']:6.1f} / {s['feeder']['setpoint_kg_h']:.0f} kg/h  "
            f"Hopper={s['feeder']['hopper_level_pct']:.1f}%",
            "=" * 60,
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"ExtruderController(state={self._state.name}, scan={self._scan_number})"
