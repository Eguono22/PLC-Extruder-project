"""Unit tests for the material feeder component."""

import pytest
from plc_extruder.components.feeder import MaterialFeeder
from plc_extruder.utils.alarms import AlarmManager, AlarmSeverity
import config


def _make_feeder(hopper_pct: float = 100.0, **kwargs) -> tuple:
    alarms = AlarmManager()
    feeder = MaterialFeeder(alarm_manager=alarms, initial_level_pct=hopper_pct, **kwargs)
    return feeder, alarms


class TestMaterialFeeder:

    # ------------------------------------------------------------------
    # Initial state
    # ------------------------------------------------------------------

    def test_initial_state_stopped(self):
        feeder, _ = _make_feeder()
        assert not feeder.is_running
        assert feeder.actual_rate == pytest.approx(0.0)

    def test_initial_hopper_level_full(self):
        feeder, _ = _make_feeder(hopper_pct=100.0)
        assert feeder.hopper_level_pct == pytest.approx(100.0)

    def test_initial_hopper_level_custom(self):
        feeder, _ = _make_feeder(hopper_pct=50.0)
        assert feeder.hopper_level_pct == pytest.approx(50.0)

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def test_start_enables_running(self):
        feeder, _ = _make_feeder()
        feeder.start()
        assert feeder.is_running

    def test_stop_disables_running(self):
        feeder, _ = _make_feeder()
        feeder.start()
        feeder.stop()
        assert not feeder.is_running

    def test_rate_zero_after_stop(self):
        feeder, _ = _make_feeder()
        feeder.start()
        feeder.set_rate(50.0)
        feeder.stop()
        assert feeder.actual_rate == pytest.approx(0.0)

    # ------------------------------------------------------------------
    # Rate clamping
    # ------------------------------------------------------------------

    def test_rate_clamped_to_min(self):
        feeder, _ = _make_feeder()
        feeder.set_rate(0.0)
        assert feeder.setpoint >= config.FEEDER_MIN_RATE

    def test_rate_clamped_to_max(self):
        feeder, _ = _make_feeder()
        feeder.set_rate(99999.0)
        assert feeder.setpoint <= config.FEEDER_MAX_RATE

    # ------------------------------------------------------------------
    # Simulation dynamics
    # ------------------------------------------------------------------

    def test_actual_rate_rises_after_start(self):
        feeder, _ = _make_feeder()
        feeder.start()
        feeder.set_rate(50.0)
        for _ in range(100):
            feeder.update(config.SCAN_CYCLE_S)
        assert feeder.actual_rate > 0.0

    def test_hopper_depletes_during_feeding(self):
        feeder, _ = _make_feeder()
        feeder.start()
        feeder.set_rate(config.FEEDER_MAX_RATE)
        initial_level = feeder.hopper_level_kg
        for _ in range(500):
            feeder.update(config.SCAN_CYCLE_S)
        assert feeder.hopper_level_kg < initial_level

    def test_no_consumption_when_stopped(self):
        feeder, _ = _make_feeder()
        feeder.stop()
        level_before = feeder.hopper_level_kg
        for _ in range(100):
            feeder.update(config.SCAN_CYCLE_S)
        assert feeder.hopper_level_kg == level_before

    # ------------------------------------------------------------------
    # Alarms
    # ------------------------------------------------------------------

    def test_low_material_alarm_raised(self):
        feeder, alarms = _make_feeder(hopper_pct=5.0)
        feeder.start()
        feeder.set_rate(50.0)
        feeder.update(config.SCAN_CYCLE_S)
        assert alarms.has_active("FEEDER_LOW_MATERIAL")

    def test_empty_hopper_triggers_fault(self):
        feeder, alarms = _make_feeder(hopper_pct=0.5)
        feeder.start()
        feeder.set_rate(50.0)
        for _ in range(50):
            feeder.update(config.SCAN_CYCLE_S)
        assert feeder.has_fault or alarms.has_active("FEEDER_EMPTY_HOPPER")

    # ------------------------------------------------------------------
    # Refill
    # ------------------------------------------------------------------

    def test_refill_increases_level(self):
        feeder, _ = _make_feeder(hopper_pct=30.0)
        before = feeder.hopper_level_kg
        feeder.refill_hopper(50.0)
        assert feeder.hopper_level_kg == pytest.approx(before + 50.0)

    def test_refill_does_not_exceed_capacity(self):
        feeder, _ = _make_feeder(hopper_pct=100.0)
        feeder.refill_hopper(9999.0)
        assert feeder.hopper_level_kg <= feeder.hopper_capacity

    # ------------------------------------------------------------------
    # Fault reset
    # ------------------------------------------------------------------

    def test_fault_reset_clears_fault(self):
        feeder, alarms = _make_feeder(hopper_pct=0.5)
        feeder.start()
        feeder.set_rate(50.0)
        for _ in range(50):
            feeder.update(config.SCAN_CYCLE_S)
        feeder.reset_fault()
        assert not feeder.has_fault

    def test_fault_reset_clears_empty_hopper_alarm(self):
        feeder, alarms = _make_feeder(hopper_pct=0.5)
        feeder.start()
        feeder.set_rate(50.0)
        for _ in range(50):
            feeder.update(config.SCAN_CYCLE_S)
        feeder.reset_fault()
        assert not alarms.has_active("FEEDER_EMPTY_HOPPER")

    # ------------------------------------------------------------------
    # Status dict
    # ------------------------------------------------------------------

    def test_status_dict_keys(self):
        feeder, _ = _make_feeder()
        d = feeder.status_dict()
        for key in ("running", "fault", "setpoint_kg_h", "actual_rate_kg_h",
                    "hopper_level_pct", "hopper_level_kg"):
            assert key in d

    def test_repr(self):
        feeder, _ = _make_feeder()
        assert "MaterialFeeder" in repr(feeder)
