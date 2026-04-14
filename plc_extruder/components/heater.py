"""
Barrel heating component – multi-zone temperature control.

Industrial extruders typically have 3–6 independently controlled barrel
heating zones, running from the feed throat (coolest) to the metering
section (hottest).  Each zone has:

* A resistive band heater (0–100 % power output from PID)
* An optional cooling valve/fan (for over-temperature correction)
* A thermocouple for process-value feedback

Physical simulation
-------------------
Temperature evolves according to a simplified first-order model:

    dT/dt = (P_heat * heat_rate - P_cool * cool_rate) / thermal_mass

where *heat_rate* and *cool_rate* are empirical constants.
"""

from __future__ import annotations

from typing import List

from plc_extruder.utils.pid import PIDController
from plc_extruder.utils.alarms import AlarmManager, AlarmSeverity
import config


class HeatingZone:
    """Single barrel heating zone.

    Args:
        zone_index: 0-based zone number (used in alarm codes).
        setpoint: Target temperature (°C).
        alarm_manager: Shared :class:`AlarmManager` instance.
        ambient_temp: Ambient / initial temperature (°C).
    """

    # Thermal simulation constants
    _THERMAL_MASS = 50.0       # °C·s / (W-equivalent unit)
    _HEAT_RATE = 8.0           # °C/s at 100 % heater output (per 100 ms scan)
    _COOL_RATE = 2.0           # °C/s at 100 % cooling

    def __init__(
        self,
        zone_index: int,
        setpoint: float,
        alarm_manager: AlarmManager,
        ambient_temp: float = 20.0,
    ) -> None:
        self.zone_index = zone_index
        self._setpoint = setpoint
        self._alarms = alarm_manager
        self._temperature = ambient_temp

        self._pid = PIDController(
            kp=config.TEMP_PID_KP,
            ki=config.TEMP_PID_KI,
            kd=config.TEMP_PID_KD,
            output_min=config.TEMP_PID_OUTPUT_MIN,
            output_max=config.TEMP_PID_OUTPUT_MAX,
        )
        self._heater_output: float = 0.0   # % (0–100)
        self._cooling_output: float = 0.0  # % (0–100)
        self._enabled: bool = False

    # ------------------------------------------------------------------
    # Alarm codes (zone-specific)
    # ------------------------------------------------------------------

    @property
    def _alm_over_temp(self) -> str:
        return f"OVER_TEMP_Z{self.zone_index + 1}"

    @property
    def _alm_under_temp(self) -> str:
        return f"UNDER_TEMP_Z{self.zone_index + 1}"

    @property
    def _alm_sensor_fault(self) -> str:
        return f"SENSOR_FAULT_Z{self.zone_index + 1}"

    # ------------------------------------------------------------------
    # Control interface
    # ------------------------------------------------------------------

    def enable(self) -> None:
        """Enable heater output for this zone."""
        self._enabled = True
        self._pid.reset()

    def disable(self) -> None:
        """Disable heater output (zone cools to ambient passively)."""
        self._enabled = False
        self._heater_output = 0.0
        self._cooling_output = 0.0

    def set_setpoint(self, temp: float) -> None:
        """Change the temperature setpoint (°C)."""
        self._setpoint = temp

    # ------------------------------------------------------------------
    # Simulation update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the zone temperature simulation by *dt* seconds.

        Args:
            dt: Time step in seconds.
        """
        # Check for safety over-temperature
        if self._temperature >= config.MAX_BARREL_TEMP:
            self._alarms.raise_alarm(
                self._alm_over_temp,
                f"Zone {self.zone_index + 1} OVER TEMPERATURE: "
                f"{self._temperature:.1f} °C",
                AlarmSeverity.CRITICAL,
            )
            # Force heater off regardless of PID
            self._heater_output = 0.0
            self._cooling_output = 100.0  # Maximum cooling
        else:
            if self._alarms.has_active(self._alm_over_temp):
                self._alarms.clear_alarm(self._alm_over_temp)

        if not self._enabled:
            # Passive cooling towards ambient (20 °C)
            self._heater_output = 0.0
            self._cooling_output = 0.0
            self._temperature += (20.0 - self._temperature) * (dt / 300.0)
            return

        # PID control – output is heater power %
        pid_output = self._pid.compute(
            setpoint=self._setpoint,
            process_value=self._temperature,
            dt=dt,
        )
        self._heater_output = pid_output

        # If over setpoint, activate cooling
        error = self._setpoint - self._temperature
        if error < -config.TEMP_TOLERANCE:
            self._cooling_output = min(100.0, abs(error) * 5.0)
        else:
            self._cooling_output = 0.0

        # Temperature dynamics
        heat_delta = self._heater_output * config.HEAT_RAMP_RATE * dt / 100.0
        cool_delta = self._cooling_output * config.COOL_RAMP_RATE * dt / 100.0
        # Passive heat loss to ambient
        ambient_loss = (self._temperature - 20.0) * 0.001 * dt
        self._temperature += heat_delta - cool_delta - ambient_loss

        # Raise warning if running but temperature is far below setpoint
        if (
            self._temperature < self._setpoint - 20.0
            and self._temperature > 20.0
        ):
            self._alarms.raise_alarm(
                self._alm_under_temp,
                f"Zone {self.zone_index + 1} low temperature: "
                f"{self._temperature:.1f} °C (SP {self._setpoint:.1f} °C)",
                AlarmSeverity.WARNING,
            )
        elif self._alarms.has_active(self._alm_under_temp):
            self._alarms.clear_alarm(self._alm_under_temp)

    # ------------------------------------------------------------------
    # Properties / status
    # ------------------------------------------------------------------

    @property
    def temperature(self) -> float:
        """Current zone temperature (°C)."""
        return self._temperature

    @property
    def setpoint(self) -> float:
        """Current temperature setpoint (°C)."""
        return self._setpoint

    @property
    def heater_output(self) -> float:
        """Heater power output (0–100 %)."""
        return self._heater_output

    @property
    def cooling_output(self) -> float:
        """Cooling output (0–100 %)."""
        return self._cooling_output

    @property
    def is_enabled(self) -> bool:
        """True if heater output is active."""
        return self._enabled

    @property
    def at_setpoint(self) -> bool:
        """True if temperature is within tolerance of the setpoint."""
        return abs(self._temperature - self._setpoint) <= config.TEMP_TOLERANCE

    def status_dict(self) -> dict:
        """Return zone state snapshot."""
        return {
            "zone": self.zone_index + 1,
            "enabled": self._enabled,
            "setpoint_c": round(self._setpoint, 1),
            "temperature_c": round(self._temperature, 2),
            "heater_output_pct": round(self._heater_output, 1),
            "cooling_output_pct": round(self._cooling_output, 1),
            "at_setpoint": self.at_setpoint,
        }

    def __repr__(self) -> str:
        return (
            f"HeatingZone({self.zone_index + 1}: "
            f"{self._temperature:.1f}/{self._setpoint:.1f} °C, "
            f"heat={self._heater_output:.0f}%)"
        )


class BarrelHeater:
    """Multi-zone barrel heater assembly.

    Manages *n* :class:`HeatingZone` instances that map to the barrel
    sections of the extruder (feed zone → metering zone).

    Args:
        alarm_manager: Shared :class:`AlarmManager` instance.
        zone_setpoints: Ordered list of setpoints (°C) for each zone.
        ambient_temp: Initial temperature of all zones (°C).
    """

    def __init__(
        self,
        alarm_manager: AlarmManager,
        zone_setpoints: List[float] = None,
        ambient_temp: float = 20.0,
    ) -> None:
        if zone_setpoints is None:
            zone_setpoints = config.BARREL_ZONE_SETPOINTS
        self._zones: List[HeatingZone] = [
            HeatingZone(i, sp, alarm_manager, ambient_temp)
            for i, sp in enumerate(zone_setpoints)
        ]

    # ------------------------------------------------------------------
    # Control interface
    # ------------------------------------------------------------------

    def enable_all(self) -> None:
        """Enable all heating zones."""
        for zone in self._zones:
            zone.enable()

    def disable_all(self) -> None:
        """Disable all heating zones."""
        for zone in self._zones:
            zone.disable()

    def set_setpoint(self, zone_index: int, temp: float) -> None:
        """Change the setpoint for a specific zone (0-based index)."""
        self._zones[zone_index].set_setpoint(temp)

    # ------------------------------------------------------------------
    # Simulation update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Update all zones for one scan cycle."""
        for zone in self._zones:
            zone.update(dt)

    # ------------------------------------------------------------------
    # Properties / status
    # ------------------------------------------------------------------

    @property
    def zones(self) -> List[HeatingZone]:
        """Ordered list of heating zones."""
        return self._zones

    @property
    def zone_count(self) -> int:
        """Number of barrel heating zones."""
        return len(self._zones)

    @property
    def all_at_setpoint(self) -> bool:
        """True if every enabled zone is within its temperature tolerance."""
        enabled_zones = [z for z in self._zones if z.is_enabled]
        return bool(enabled_zones) and all(z.at_setpoint for z in enabled_zones)

    @property
    def temperatures(self) -> List[float]:
        """Current temperatures of all zones (°C), ordered zone 1 → n."""
        return [z.temperature for z in self._zones]

    def status_dict(self) -> dict:
        """Return a full heater assembly snapshot."""
        return {
            "all_at_setpoint": self.all_at_setpoint,
            "zones": [z.status_dict() for z in self._zones],
        }

    def __repr__(self) -> str:
        temps = ", ".join(f"{z.temperature:.1f}" for z in self._zones)
        return f"BarrelHeater([{temps}] °C, at_sp={self.all_at_setpoint})"
