"""Unit tests for the barrel heater and heating zone components."""

import pytest
from plc_extruder.components.heater import HeatingZone, BarrelHeater
from plc_extruder.utils.alarms import AlarmManager, AlarmSeverity
import config


def _alm() -> AlarmManager:
    return AlarmManager()


class TestHeatingZone:

    def _zone(self, setpoint: float = 200.0, ambient: float = 20.0) -> tuple:
        alarms = _alm()
        zone = HeatingZone(
            zone_index=0,
            setpoint=setpoint,
            alarm_manager=alarms,
            ambient_temp=ambient,
        )
        return zone, alarms

    # ------------------------------------------------------------------
    # Initial state
    # ------------------------------------------------------------------

    def test_initial_disabled(self):
        zone, _ = self._zone()
        assert not zone.is_enabled

    def test_initial_temperature_is_ambient(self):
        zone, _ = self._zone(ambient=25.0)
        assert zone.temperature == pytest.approx(25.0)

    # ------------------------------------------------------------------
    # Enable / disable
    # ------------------------------------------------------------------

    def test_enable_sets_flag(self):
        zone, _ = self._zone()
        zone.enable()
        assert zone.is_enabled

    def test_disable_clears_flag(self):
        zone, _ = self._zone()
        zone.enable()
        zone.disable()
        assert not zone.is_enabled

    def test_heater_output_zero_when_disabled(self):
        zone, _ = self._zone()
        zone.update(dt=0.1)
        assert zone.heater_output == pytest.approx(0.0)

    # ------------------------------------------------------------------
    # Temperature dynamics
    # ------------------------------------------------------------------

    def test_temperature_rises_when_enabled(self):
        zone, _ = self._zone(setpoint=200.0, ambient=20.0)
        zone.enable()
        initial = zone.temperature
        for _ in range(50):
            zone.update(dt=config.SCAN_CYCLE_S)
        assert zone.temperature > initial

    def test_temperature_cools_when_disabled(self):
        zone, _ = self._zone(setpoint=200.0, ambient=20.0)
        zone._temperature = 200.0  # set artificially high
        zone.disable()
        for _ in range(100):
            zone.update(dt=config.SCAN_CYCLE_S)
        assert zone.temperature < 200.0

    def test_setpoint_change_accepted(self):
        zone, _ = self._zone(setpoint=200.0)
        zone.set_setpoint(220.0)
        assert zone.setpoint == pytest.approx(220.0)

    # ------------------------------------------------------------------
    # Alarms
    # ------------------------------------------------------------------

    def test_over_temp_alarm_raised(self):
        zone, alarms = self._zone()
        zone.enable()
        zone._temperature = config.MAX_BARREL_TEMP + 1.0
        zone.update(dt=config.SCAN_CYCLE_S)
        assert alarms.has_active("OVER_TEMP_Z1")

    def test_over_temp_disables_heater(self):
        zone, alarms = self._zone()
        zone.enable()
        zone._temperature = config.MAX_BARREL_TEMP + 5.0
        zone.update(dt=config.SCAN_CYCLE_S)
        assert zone.heater_output == pytest.approx(0.0)

    def test_at_setpoint_when_close(self):
        zone, _ = self._zone(setpoint=200.0)
        zone._temperature = 202.0
        assert zone.at_setpoint

    def test_not_at_setpoint_when_far(self):
        zone, _ = self._zone(setpoint=200.0)
        zone._temperature = 150.0
        assert not zone.at_setpoint

    # ------------------------------------------------------------------
    # Status dict
    # ------------------------------------------------------------------

    def test_status_dict_keys(self):
        zone, _ = self._zone()
        d = zone.status_dict()
        for key in ("zone", "enabled", "setpoint_c", "temperature_c",
                    "heater_output_pct", "at_setpoint"):
            assert key in d

    def test_repr(self):
        zone, _ = self._zone()
        assert "HeatingZone" in repr(zone)


class TestBarrelHeater:

    def _heater(self, setpoints=None) -> tuple:
        alarms = _alm()
        heater = BarrelHeater(alarm_manager=alarms, zone_setpoints=setpoints)
        return heater, alarms

    def test_correct_zone_count(self):
        heater, _ = self._heater([200.0, 210.0, 220.0])
        assert heater.zone_count == 3

    def test_default_zone_count_from_config(self):
        heater, _ = self._heater()
        assert heater.zone_count == config.BARREL_ZONE_COUNT

    def test_enable_all_enables_every_zone(self):
        heater, _ = self._heater()
        heater.enable_all()
        assert all(z.is_enabled for z in heater.zones)

    def test_disable_all_disables_every_zone(self):
        heater, _ = self._heater()
        heater.enable_all()
        heater.disable_all()
        assert all(not z.is_enabled for z in heater.zones)

    def test_temperatures_list_length(self):
        heater, _ = self._heater()
        assert len(heater.temperatures) == heater.zone_count

    def test_all_at_setpoint_initially_false_cold(self):
        heater, _ = self._heater()
        heater.enable_all()
        # At 20 °C, zones are far below their setpoints
        assert not heater.all_at_setpoint

    def test_all_at_setpoint_when_at_temp(self):
        heater, _ = self._heater()
        heater.enable_all()
        # Force all zones to setpoint
        for zone in heater.zones:
            zone._temperature = zone.setpoint
        assert heater.all_at_setpoint

    def test_update_advances_all_zones(self):
        heater, _ = self._heater()
        heater.enable_all()
        temps_before = list(heater.temperatures)
        for _ in range(20):
            heater.update(config.SCAN_CYCLE_S)
        temps_after = heater.temperatures
        assert any(a > b for a, b in zip(temps_after, temps_before))

    def test_set_setpoint_for_specific_zone(self):
        heater, _ = self._heater()
        heater.set_setpoint(0, 250.0)
        assert heater.zones[0].setpoint == pytest.approx(250.0)

    def test_status_dict_contains_zones(self):
        heater, _ = self._heater()
        d = heater.status_dict()
        assert "zones" in d
        assert len(d["zones"]) == heater.zone_count

    def test_repr(self):
        heater, _ = self._heater()
        assert "BarrelHeater" in repr(heater)
