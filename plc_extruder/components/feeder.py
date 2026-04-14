"""
Material feeder component.

The feeder controls the gravimetric/volumetric delivery of raw plastic
pellets (or powder) from the hopper into the extruder barrel.  A PID
loop maintains the commanded feed rate by adjusting the auger/belt speed.

Physical simulation
-------------------
Each :meth:`update` call advances the feeder by *dt* seconds:

* Hopper material level decreases proportionally to the actual feed rate.
* The actual feed rate tracks the setpoint via a first-order lag
  (emulating the mechanical response of the auger drive).
"""

from __future__ import annotations

from plc_extruder.utils.pid import PIDController
from plc_extruder.utils.alarms import AlarmManager, AlarmSeverity
import config


class MaterialFeeder:
    """Gravimetric material feeder with hopper level monitoring.

    Args:
        alarm_manager: Shared :class:`AlarmManager` instance.
        max_rate: Maximum feed rate (kg/h).
        hopper_capacity: Hopper capacity (kg).
        initial_level_pct: Starting hopper fill level (0–100 %).
    """

    # Alarm codes
    _ALM_LOW_MATERIAL = "FEEDER_LOW_MATERIAL"
    _ALM_EMPTY_HOPPER = "FEEDER_EMPTY_HOPPER"
    _ALM_FEEDER_FAULT = "FEEDER_FAULT"

    def __init__(
        self,
        alarm_manager: AlarmManager,
        max_rate: float = config.FEEDER_MAX_RATE,
        hopper_capacity: float = config.FEEDER_HOPPER_CAPACITY,
        initial_level_pct: float = 100.0,
    ) -> None:
        self._alarms = alarm_manager
        self.max_rate = max_rate
        self.min_rate = config.FEEDER_MIN_RATE
        self.hopper_capacity = hopper_capacity

        # State
        self._hopper_level_kg: float = hopper_capacity * (initial_level_pct / 100.0)
        self._setpoint: float = 0.0        # kg/h commanded
        self._actual_rate: float = 0.0     # kg/h measured (simulated)
        self._running: bool = False
        self._fault: bool = False

        # PID for auger speed → feed rate
        self._pid = PIDController(
            kp=config.FEED_PID_KP,
            ki=config.FEED_PID_KI,
            kd=config.FEED_PID_KD,
            output_min=0.0,
            output_max=100.0,
        )

        # First-order lag time constant for mechanical response (seconds)
        self._lag_tc: float = 3.0

    # ------------------------------------------------------------------
    # Control interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Enable the feeder drive."""
        if not self._fault:
            self._running = True
            self._pid.reset()

    def stop(self) -> None:
        """Stop the feeder (setpoint is preserved for restart)."""
        self._running = False
        self._actual_rate = 0.0

    def set_rate(self, rate_kg_h: float) -> None:
        """Set the desired feed rate in kg/h.

        The value is clamped to [min_rate, max_rate] when the feeder is
        running, or set to zero when stopped.
        """
        self._setpoint = max(self.min_rate, min(self.max_rate, rate_kg_h))

    def reset_fault(self) -> None:
        """Clear the feeder fault flag and acknowledge related alarms."""
        self._fault = False
        self._alarms.clear_alarm(self._ALM_FEEDER_FAULT)

    # ------------------------------------------------------------------
    # Simulation update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the feeder simulation by *dt* seconds.

        Args:
            dt: Time step in seconds (should equal the PLC scan cycle).
        """
        if not self._running or self._fault:
            self._actual_rate = 0.0
            self._pid.reset()
            return

        if self.hopper_level_pct <= config.EMPTY_MATERIAL_LEVEL:
            # Hopper empty – cannot feed
            self._alarms.raise_alarm(
                self._ALM_EMPTY_HOPPER,
                "Hopper empty – material feed interrupted",
                AlarmSeverity.FAULT,
            )
            self._fault = True
            self._actual_rate = 0.0
            return

        # Clear empty-hopper alarm if level has been restored
        if self._alarms.has_active(self._ALM_EMPTY_HOPPER):
            self._alarms.clear_alarm(self._ALM_EMPTY_HOPPER)

        # Raise / clear low-material warning
        if self.hopper_level_pct <= config.LOW_MATERIAL_LEVEL:
            self._alarms.raise_alarm(
                self._ALM_LOW_MATERIAL,
                f"Low hopper level: {self.hopper_level_pct:.1f} %",
                AlarmSeverity.WARNING,
            )
        elif self._alarms.has_active(self._ALM_LOW_MATERIAL):
            self._alarms.clear_alarm(self._ALM_LOW_MATERIAL)

        # PID → auger drive output (%)
        drive_pct = self._pid.compute(
            setpoint=self._setpoint,
            process_value=self._actual_rate,
            dt=dt,
        )

        # Target rate from drive output
        target_rate = (drive_pct / 100.0) * self.max_rate

        # First-order lag: actual_rate → target_rate
        alpha = dt / (self._lag_tc + dt)
        self._actual_rate += alpha * (target_rate - self._actual_rate)

        # Consume material from hopper (convert kg/h → kg/scan)
        consumed_kg = self._actual_rate * (dt / 3600.0)
        self._hopper_level_kg = max(0.0, self._hopper_level_kg - consumed_kg)

    # ------------------------------------------------------------------
    # Properties / status
    # ------------------------------------------------------------------

    @property
    def actual_rate(self) -> float:
        """Current feed rate in kg/h."""
        return self._actual_rate

    @property
    def setpoint(self) -> float:
        """Commanded feed rate setpoint in kg/h."""
        return self._setpoint

    @property
    def hopper_level_kg(self) -> float:
        """Remaining material in hopper (kg)."""
        return self._hopper_level_kg

    @property
    def hopper_level_pct(self) -> float:
        """Remaining material as a percentage of hopper capacity (0–100 %)."""
        return (self._hopper_level_kg / self.hopper_capacity) * 100.0

    @property
    def is_running(self) -> bool:
        """True if the feeder drive is enabled."""
        return self._running

    @property
    def has_fault(self) -> bool:
        """True if a non-clearable fault has been detected."""
        return self._fault

    def refill_hopper(self, kg: float) -> None:
        """Add material to the hopper (e.g. after a refill cycle).

        Args:
            kg: Amount of material to add (kg).
        """
        self._hopper_level_kg = min(
            self.hopper_capacity, self._hopper_level_kg + kg
        )

    def status_dict(self) -> dict:
        """Return a snapshot of feeder state suitable for logging/HMI."""
        return {
            "running": self._running,
            "fault": self._fault,
            "setpoint_kg_h": round(self._setpoint, 2),
            "actual_rate_kg_h": round(self._actual_rate, 2),
            "hopper_level_pct": round(self.hopper_level_pct, 1),
            "hopper_level_kg": round(self._hopper_level_kg, 2),
        }

    def __repr__(self) -> str:
        return (
            f"MaterialFeeder(rate={self._actual_rate:.1f}/{self._setpoint:.1f} kg/h, "
            f"hopper={self.hopper_level_pct:.1f}%)"
        )
