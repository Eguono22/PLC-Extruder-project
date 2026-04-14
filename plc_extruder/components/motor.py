"""
Extrusion motor / screw drive component.

The motor drives the extruder screw, creating the shear force responsible
for melting and mixing the polymer.  A Variable Frequency Drive (VFD)
controls the motor speed; PID maintains the commanded RPM setpoint.

Physical simulation
-------------------
* Motor current is estimated from torque load (proportional to melt
  viscosity pressure build-up in the barrel).
* Screw RPM follows the VFD command with a short mechanical lag.
* High current triggers an overload alarm.
"""

from __future__ import annotations

from plc_extruder.utils.pid import PIDController
from plc_extruder.utils.alarms import AlarmManager, AlarmSeverity
import config


class ExtrusionMotor:
    """VFD-controlled extruder screw motor.

    Args:
        alarm_manager: Shared :class:`AlarmManager` instance.
        max_rpm: Maximum screw speed (RPM).
        rated_current: Motor rated current (A).
    """

    # Alarm codes
    _ALM_OVERCURRENT = "MOTOR_OVERCURRENT"
    _ALM_OVERSPEED = "MOTOR_OVERSPEED"
    _ALM_STALL = "MOTOR_STALL"

    def __init__(
        self,
        alarm_manager: AlarmManager,
        max_rpm: float = config.MOTOR_MAX_RPM,
        rated_current: float = config.MAX_MOTOR_CURRENT,
    ) -> None:
        self._alarms = alarm_manager
        self.max_rpm = max_rpm
        self.min_rpm = config.MOTOR_MIN_RPM
        self.rated_current = rated_current

        # State
        self._setpoint_rpm: float = 0.0
        self._actual_rpm: float = 0.0
        self._vfd_output_pct: float = 0.0   # 0–100 % VFD output
        self._current_a: float = 0.0
        self._torque_pct: float = 0.0       # % of rated torque
        self._running: bool = False
        self._fault: bool = False

        # Speed PID
        self._pid = PIDController(
            kp=config.SPEED_PID_KP,
            ki=config.SPEED_PID_KI,
            kd=config.SPEED_PID_KD,
            output_min=config.SPEED_PID_OUTPUT_MIN,
            output_max=config.SPEED_PID_OUTPUT_MAX,
        )

        # Mechanical lag time constant (seconds)
        self._lag_tc: float = 1.5

        # Simulated melt back-pressure coefficient (affects torque)
        self._backpressure_coef: float = 0.6

    # ------------------------------------------------------------------
    # Control interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Enable the motor (VFD enabled)."""
        if not self._fault:
            self._running = True
            self._pid.reset()

    def stop(self) -> None:
        """Ramp motor to zero and disable VFD."""
        self._running = False
        self._setpoint_rpm = 0.0

    def set_speed(self, rpm: float) -> None:
        """Set the target screw speed in RPM.

        Args:
            rpm: Desired RPM, clamped to [min_rpm, max_rpm].
        """
        self._setpoint_rpm = max(self.min_rpm, min(self.max_rpm, rpm))

    def reset_fault(self) -> None:
        """Clear motor fault state and acknowledge related alarms."""
        self._fault = False
        for code in (self._ALM_OVERCURRENT, self._ALM_OVERSPEED, self._ALM_STALL):
            self._alarms.clear_alarm(code)

    # ------------------------------------------------------------------
    # Simulation update
    # ------------------------------------------------------------------

    def update(self, dt: float, melt_pressure_bar: float = 0.0) -> None:
        """Advance motor simulation by *dt* seconds.

        Args:
            dt: Time step in seconds.
            melt_pressure_bar: Current melt pressure in the barrel (bar),
                used to model load torque.
        """
        if not self._running or self._fault:
            # Decelerate to stop with a time constant
            alpha = dt / (self._lag_tc + dt)
            self._actual_rpm += alpha * (0.0 - self._actual_rpm)
            self._vfd_output_pct = 0.0
            self._current_a = 0.0
            self._torque_pct = 0.0
            if self._actual_rpm < 0.1:
                self._actual_rpm = 0.0
            return

        # PID → VFD output
        vfd_pct = self._pid.compute(
            setpoint=self._setpoint_rpm,
            process_value=self._actual_rpm,
            dt=dt,
        )
        self._vfd_output_pct = vfd_pct
        target_rpm = (vfd_pct / 100.0) * self.max_rpm

        # First-order lag for mechanical response
        alpha = dt / (self._lag_tc + dt)
        self._actual_rpm += alpha * (target_rpm - self._actual_rpm)

        # Torque: combination of viscous drag and back-pressure load
        speed_load = (self._actual_rpm / self.max_rpm) * 40.0  # base load %
        pressure_load = (melt_pressure_bar / config.DIE_MAX_PRESSURE) * 60.0
        self._torque_pct = min(100.0, speed_load + pressure_load * self._backpressure_coef)

        # Estimated motor current
        self._current_a = (self._torque_pct / 100.0) * self.rated_current

        # Over-current protection
        if self._current_a >= config.MAX_MOTOR_CURRENT:
            self._alarms.raise_alarm(
                self._ALM_OVERCURRENT,
                f"Motor over-current: {self._current_a:.1f} A "
                f"(limit {config.MAX_MOTOR_CURRENT:.0f} A)",
                AlarmSeverity.FAULT,
            )
            self._fault = True
        else:
            if self._alarms.has_active(self._ALM_OVERCURRENT):
                self._alarms.clear_alarm(self._ALM_OVERCURRENT)

        # Over-speed protection
        if self._actual_rpm > self.max_rpm * 1.05:
            self._alarms.raise_alarm(
                self._ALM_OVERSPEED,
                f"Motor over-speed: {self._actual_rpm:.1f} RPM",
                AlarmSeverity.FAULT,
            )
            self._fault = True

        # Torque overload warning
        if self._torque_pct >= config.MAX_MOTOR_TORQUE:
            self._alarms.raise_alarm(
                self._ALM_STALL,
                f"Motor torque overload: {self._torque_pct:.1f} %",
                AlarmSeverity.WARNING,
            )
        elif self._alarms.has_active(self._ALM_STALL):
            self._alarms.clear_alarm(self._ALM_STALL)

    # ------------------------------------------------------------------
    # Properties / status
    # ------------------------------------------------------------------

    @property
    def actual_rpm(self) -> float:
        """Current screw speed (RPM)."""
        return self._actual_rpm

    @property
    def setpoint_rpm(self) -> float:
        """Commanded screw speed setpoint (RPM)."""
        return self._setpoint_rpm

    @property
    def current_a(self) -> float:
        """Estimated motor current (A)."""
        return self._current_a

    @property
    def torque_pct(self) -> float:
        """Estimated torque as percentage of rated torque."""
        return self._torque_pct

    @property
    def vfd_output_pct(self) -> float:
        """VFD drive output (0–100 %)."""
        return self._vfd_output_pct

    @property
    def is_running(self) -> bool:
        """True if the motor drive is enabled."""
        return self._running

    @property
    def has_fault(self) -> bool:
        """True if a fault condition has been detected."""
        return self._fault

    def status_dict(self) -> dict:
        """Return a motor state snapshot."""
        return {
            "running": self._running,
            "fault": self._fault,
            "setpoint_rpm": round(self._setpoint_rpm, 1),
            "actual_rpm": round(self._actual_rpm, 2),
            "vfd_output_pct": round(self._vfd_output_pct, 1),
            "current_a": round(self._current_a, 2),
            "torque_pct": round(self._torque_pct, 1),
        }

    def __repr__(self) -> str:
        return (
            f"ExtrusionMotor(rpm={self._actual_rpm:.1f}/{self._setpoint_rpm:.1f}, "
            f"I={self._current_a:.1f} A, T={self._torque_pct:.0f}%)"
        )
