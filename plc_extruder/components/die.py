"""
Die / head zone component.

The die (or head) is the terminal section of the extruder where the
molten polymer is forced through a shaped orifice to produce the final
cross-section (film, pipe, profile, etc.).

Key parameters monitored here:

* **Die temperature** – controlled by a band heater + PID (same model as
  barrel zones).  Die temperature strongly affects surface quality.
* **Melt pressure** – the back-pressure upstream of the die orifice.
  Derived from screw speed, die restriction coefficient, and melt
  temperature (viscosity).
* **Throughput** – estimated mass-flow rate (kg/h) through the die.

Physical simulation
-------------------
Melt pressure is modelled as::

    P = k_die * screw_rpm * viscosity_factor / die_opening_pct

where *viscosity_factor* decreases with rising melt temperature
(polymer melt viscosity decreases with temperature).
"""

from __future__ import annotations

from plc_extruder.utils.pid import PIDController
from plc_extruder.utils.alarms import AlarmManager, AlarmSeverity
import config


class DieZone:
    """Extruder die / head control zone.

    Args:
        alarm_manager: Shared :class:`AlarmManager` instance.
        setpoint: Die temperature setpoint (°C).
        die_opening_pct: Die orifice opening as % (100 % = fully open).
        ambient_temp: Initial die temperature (°C).
    """

    # Alarm codes
    _ALM_OVER_TEMP = "DIE_OVER_TEMP"
    _ALM_OVER_PRESSURE = "DIE_OVER_PRESSURE"
    _ALM_PRESSURE_WARN = "DIE_PRESSURE_HIGH"

    # Pressure model constant
    _PRESSURE_COEF = 1.8       # bar · min / RPM

    def __init__(
        self,
        alarm_manager: AlarmManager,
        setpoint: float = config.DIE_ZONE_SETPOINT,
        die_opening_pct: float = 100.0,
        ambient_temp: float = 20.0,
    ) -> None:
        self._alarms = alarm_manager
        self._setpoint = setpoint
        self._die_opening_pct = max(5.0, min(100.0, die_opening_pct))
        self._temperature = ambient_temp

        self._pid = PIDController(
            kp=config.TEMP_PID_KP,
            ki=config.TEMP_PID_KI,
            kd=config.TEMP_PID_KD,
            output_min=config.TEMP_PID_OUTPUT_MIN,
            output_max=config.TEMP_PID_OUTPUT_MAX,
        )

        self._heater_output: float = 0.0
        self._melt_pressure_bar: float = 0.0
        self._throughput_kg_h: float = 0.0
        self._enabled: bool = False

    # ------------------------------------------------------------------
    # Control interface
    # ------------------------------------------------------------------

    def enable(self) -> None:
        """Enable die heater."""
        self._enabled = True
        self._pid.reset()

    def disable(self) -> None:
        """Disable die heater."""
        self._enabled = False
        self._heater_output = 0.0

    def set_setpoint(self, temp: float) -> None:
        """Change the die temperature setpoint (°C)."""
        self._setpoint = temp

    def set_die_opening(self, pct: float) -> None:
        """Adjust the die opening restriction (5–100 %)."""
        self._die_opening_pct = max(5.0, min(100.0, pct))

    # ------------------------------------------------------------------
    # Simulation update
    # ------------------------------------------------------------------

    def update(
        self,
        dt: float,
        screw_rpm: float = 0.0,
        feed_rate_kg_h: float = 0.0,
    ) -> None:
        """Advance die simulation by *dt* seconds.

        Args:
            dt: Time step in seconds.
            screw_rpm: Current screw speed (RPM).
            feed_rate_kg_h: Current feeder rate (kg/h), used for
                throughput estimation.
        """
        self._update_temperature(dt)
        self._update_pressure(screw_rpm)
        self._update_throughput(feed_rate_kg_h, screw_rpm)

    def _update_temperature(self, dt: float) -> None:
        """PID-based die temperature control."""
        if not self._enabled:
            self._heater_output = 0.0
            self._temperature += (20.0 - self._temperature) * (dt / 300.0)
            return

        if self._temperature >= config.MAX_BARREL_TEMP:
            self._alarms.raise_alarm(
                self._ALM_OVER_TEMP,
                f"Die over temperature: {self._temperature:.1f} °C",
                AlarmSeverity.CRITICAL,
            )
            self._heater_output = 0.0
            return
        if self._alarms.has_active(self._ALM_OVER_TEMP):
            self._alarms.clear_alarm(self._ALM_OVER_TEMP)

        self._heater_output = self._pid.compute(
            setpoint=self._setpoint,
            process_value=self._temperature,
            dt=dt,
        )
        heat_delta = self._heater_output * config.HEAT_RAMP_RATE * dt / 100.0
        ambient_loss = (self._temperature - 20.0) * 0.001 * dt
        self._temperature += heat_delta - ambient_loss

    def _update_pressure(self, screw_rpm: float) -> None:
        """Estimate melt pressure from screw speed and die geometry."""
        if screw_rpm <= 0.0:
            self._melt_pressure_bar = 0.0
            return

        # Viscosity factor: higher temperature → lower viscosity → lower pressure
        viscosity_factor = max(0.2, 1.0 - (self._temperature - 100.0) / 300.0)
        raw_pressure = (
            self._PRESSURE_COEF * screw_rpm * viscosity_factor
            / (self._die_opening_pct / 100.0)
        )
        self._melt_pressure_bar = min(raw_pressure, config.DIE_MAX_PRESSURE * 1.1)

        if self._melt_pressure_bar >= config.DIE_MAX_PRESSURE:
            self._alarms.raise_alarm(
                self._ALM_OVER_PRESSURE,
                f"Die over pressure: {self._melt_pressure_bar:.1f} bar",
                AlarmSeverity.CRITICAL,
            )
        else:
            if self._alarms.has_active(self._ALM_OVER_PRESSURE):
                self._alarms.clear_alarm(self._ALM_OVER_PRESSURE)

        if self._melt_pressure_bar >= config.DIE_PRESSURE_WARNING:
            self._alarms.raise_alarm(
                self._ALM_PRESSURE_WARN,
                f"Die pressure high: {self._melt_pressure_bar:.1f} bar",
                AlarmSeverity.WARNING,
            )
        elif self._alarms.has_active(self._ALM_PRESSURE_WARN):
            self._alarms.clear_alarm(self._ALM_PRESSURE_WARN)

    def _update_throughput(self, feed_rate_kg_h: float, screw_rpm: float) -> None:
        """Estimate actual throughput through the die."""
        if screw_rpm <= 0:
            self._throughput_kg_h = 0.0
            return
        # Throughput is primarily governed by screw conveyance
        rpm_fraction = screw_rpm / config.MOTOR_MAX_RPM
        self._throughput_kg_h = feed_rate_kg_h * rpm_fraction

    # ------------------------------------------------------------------
    # Properties / status
    # ------------------------------------------------------------------

    @property
    def temperature(self) -> float:
        """Current die temperature (°C)."""
        return self._temperature

    @property
    def setpoint(self) -> float:
        """Die temperature setpoint (°C)."""
        return self._setpoint

    @property
    def melt_pressure_bar(self) -> float:
        """Estimated melt pressure at the die (bar)."""
        return self._melt_pressure_bar

    @property
    def throughput_kg_h(self) -> float:
        """Estimated output throughput (kg/h)."""
        return self._throughput_kg_h

    @property
    def heater_output(self) -> float:
        """Die heater power output (0–100 %)."""
        return self._heater_output

    @property
    def is_enabled(self) -> bool:
        """True if die heater is active."""
        return self._enabled

    @property
    def at_setpoint(self) -> bool:
        """True if die temperature is within tolerance."""
        return abs(self._temperature - self._setpoint) <= config.DIE_TEMP_TOLERANCE

    def status_dict(self) -> dict:
        """Return a die state snapshot."""
        return {
            "enabled": self._enabled,
            "setpoint_c": round(self._setpoint, 1),
            "temperature_c": round(self._temperature, 2),
            "heater_output_pct": round(self._heater_output, 1),
            "melt_pressure_bar": round(self._melt_pressure_bar, 2),
            "throughput_kg_h": round(self._throughput_kg_h, 2),
            "die_opening_pct": round(self._die_opening_pct, 1),
            "at_setpoint": self.at_setpoint,
        }

    def __repr__(self) -> str:
        return (
            f"DieZone(T={self._temperature:.1f}/{self._setpoint:.1f} °C, "
            f"P={self._melt_pressure_bar:.1f} bar, "
            f"Q={self._throughput_kg_h:.1f} kg/h)"
        )
