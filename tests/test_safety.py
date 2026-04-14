"""Unit tests for the safety system component."""

import pytest
from plc_extruder.components.safety import SafetySystem, SafetyState
from plc_extruder.components.heater import BarrelHeater
from plc_extruder.components.motor import ExtrusionMotor
from plc_extruder.components.die import DieZone
from plc_extruder.components.feeder import MaterialFeeder
from plc_extruder.utils.alarms import AlarmManager
import config


def _make_components():
    alarms = AlarmManager()
    heater = BarrelHeater(alarm_manager=alarms)
    motor = ExtrusionMotor(alarm_manager=alarms)
    die = DieZone(alarm_manager=alarms)
    feeder = MaterialFeeder(alarm_manager=alarms)
    safety = SafetySystem(alarm_manager=alarms)
    return safety, heater, motor, die, feeder, alarms


class TestSafetySystem:

    # ------------------------------------------------------------------
    # Initial state
    # ------------------------------------------------------------------

    def test_initial_state_safe(self):
        safety, heater, motor, die, feeder, _ = _make_components()
        state = safety.evaluate(heater, motor, die, feeder)
        assert state == SafetyState.SAFE

    def test_no_estop_initially(self):
        safety, _, _, _, _, _ = _make_components()
        assert not safety.is_estop_active

    # ------------------------------------------------------------------
    # Hardware E-Stop
    # ------------------------------------------------------------------

    def test_hw_estop_triggers_estop_state(self):
        safety, heater, motor, die, feeder, alarms = _make_components()
        safety.trigger_estop_hardware()
        state = safety.evaluate(heater, motor, die, feeder)
        assert state == SafetyState.E_STOP

    def test_hw_estop_reset(self):
        safety, heater, motor, die, feeder, alarms = _make_components()
        safety.trigger_estop_hardware()
        safety.evaluate(heater, motor, die, feeder)
        safety.reset_estop_hardware()
        state = safety.evaluate(heater, motor, die, feeder)
        assert state == SafetyState.SAFE

    # ------------------------------------------------------------------
    # Software E-Stop
    # ------------------------------------------------------------------

    def test_sw_estop_triggers_estop_state(self):
        safety, heater, motor, die, feeder, _ = _make_components()
        safety.trigger_estop_software()
        state = safety.evaluate(heater, motor, die, feeder)
        assert state == SafetyState.E_STOP

    def test_sw_estop_cleared_by_reset_all(self):
        safety, heater, motor, die, feeder, _ = _make_components()
        safety.trigger_estop_software()
        safety.evaluate(heater, motor, die, feeder)
        safety.reset_all()
        state = safety.evaluate(heater, motor, die, feeder)
        assert state == SafetyState.SAFE

    # ------------------------------------------------------------------
    # Thermal interlock
    # ------------------------------------------------------------------

    def test_over_temp_triggers_estop(self):
        safety, heater, motor, die, feeder, _ = _make_components()
        # Force a zone over the safety limit
        heater.zones[0]._temperature = config.MAX_BARREL_TEMP + 5.0
        state = safety.evaluate(heater, motor, die, feeder)
        assert state == SafetyState.E_STOP

    def test_over_temp_alarm_raised(self):
        safety, heater, motor, die, feeder, alarms = _make_components()
        heater.zones[1]._temperature = config.MAX_BARREL_TEMP + 1.0
        safety.evaluate(heater, motor, die, feeder)
        assert alarms.has_active("SAFETY_INTERLOCK_TEMP")

    # ------------------------------------------------------------------
    # Pressure interlock
    # ------------------------------------------------------------------

    def test_over_pressure_triggers_estop(self):
        safety, heater, motor, die, feeder, _ = _make_components()
        die._melt_pressure_bar = config.DIE_MAX_PRESSURE + 1.0
        state = safety.evaluate(heater, motor, die, feeder)
        assert state == SafetyState.E_STOP

    # ------------------------------------------------------------------
    # Motor fault interlock
    # ------------------------------------------------------------------

    def test_motor_fault_triggers_estop(self):
        safety, heater, motor, die, feeder, _ = _make_components()
        motor._fault = True
        state = safety.evaluate(heater, motor, die, feeder)
        assert state == SafetyState.E_STOP

    # ------------------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------------------

    def test_watchdog_fires_without_pet(self):
        safety, heater, motor, die, feeder, alarms = _make_components()
        # Exhaust watchdog counter without petting
        for _ in range(safety._watchdog_limit + 2):
            safety.evaluate(heater, motor, die, feeder)
        assert alarms.has_active("SAFETY_WATCHDOG")

    def test_watchdog_reset_by_pet(self):
        safety, heater, motor, die, feeder, _ = _make_components()
        for _ in range(50):
            safety.pet_watchdog()
            safety.evaluate(heater, motor, die, feeder)
        # Should remain SAFE after regular petting
        state = safety.state
        assert state == SafetyState.SAFE

    # ------------------------------------------------------------------
    # Reset all
    # ------------------------------------------------------------------

    def test_reset_all_clears_estop(self):
        safety, heater, motor, die, feeder, _ = _make_components()
        safety.trigger_estop_software()
        safety.evaluate(heater, motor, die, feeder)
        safety.reset_all()
        assert not safety.is_estop_active

    def test_reset_all_resets_watchdog_counter(self):
        safety, heater, motor, die, feeder, _ = _make_components()
        for _ in range(safety._watchdog_limit + 2):
            safety.evaluate(heater, motor, die, feeder)
        safety.reset_all()
        assert safety.status_dict()["scan_count"] == 0

    # ------------------------------------------------------------------
    # Status dict / repr
    # ------------------------------------------------------------------

    def test_status_dict_keys(self):
        safety, _, _, _, _, _ = _make_components()
        d = safety.status_dict()
        for key in ("state", "estop_hw", "estop_sw", "is_estop_active"):
            assert key in d

    def test_repr(self):
        safety, _, _, _, _, _ = _make_components()
        assert "SafetySystem" in repr(safety)
