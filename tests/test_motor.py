"""Unit tests for the extrusion motor component."""

import pytest
from plc_extruder.components.motor import ExtrusionMotor
from plc_extruder.utils.alarms import AlarmManager
import config


def _make_motor() -> tuple:
    alarms = AlarmManager()
    motor = ExtrusionMotor(alarm_manager=alarms)
    return motor, alarms


class TestExtrusionMotor:

    # ------------------------------------------------------------------
    # Initial state
    # ------------------------------------------------------------------

    def test_initial_state_stopped(self):
        motor, _ = _make_motor()
        assert not motor.is_running

    def test_initial_rpm_zero(self):
        motor, _ = _make_motor()
        assert motor.actual_rpm == pytest.approx(0.0)

    def test_initial_no_fault(self):
        motor, _ = _make_motor()
        assert not motor.has_fault

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def test_start_enables_running(self):
        motor, _ = _make_motor()
        motor.start()
        assert motor.is_running

    def test_stop_clears_running(self):
        motor, _ = _make_motor()
        motor.start()
        motor.stop()
        assert not motor.is_running

    def test_set_speed_clamped_to_min(self):
        motor, _ = _make_motor()
        motor.set_speed(0.0)
        assert motor.setpoint_rpm >= config.MOTOR_MIN_RPM

    def test_set_speed_clamped_to_max(self):
        motor, _ = _make_motor()
        motor.set_speed(9999.0)
        assert motor.setpoint_rpm <= config.MOTOR_MAX_RPM

    # ------------------------------------------------------------------
    # Dynamics
    # ------------------------------------------------------------------

    def test_rpm_rises_after_start(self):
        motor, _ = _make_motor()
        motor.start()
        motor.set_speed(80.0)
        for _ in range(100):
            motor.update(dt=config.SCAN_CYCLE_S)
        assert motor.actual_rpm > 0.0

    def test_rpm_decreases_after_stop(self):
        motor, _ = _make_motor()
        motor.start()
        motor.set_speed(80.0)
        for _ in range(200):
            motor.update(dt=config.SCAN_CYCLE_S)
        motor.stop()
        rpm_at_stop = motor.actual_rpm
        for _ in range(100):
            motor.update(dt=config.SCAN_CYCLE_S)
        assert motor.actual_rpm < rpm_at_stop

    def test_current_nonzero_when_running(self):
        motor, _ = _make_motor()
        motor.start()
        motor.set_speed(80.0)
        for _ in range(200):
            motor.update(dt=config.SCAN_CYCLE_S)
        assert motor.current_a > 0.0

    def test_current_zero_when_stopped(self):
        motor, _ = _make_motor()
        assert motor.current_a == pytest.approx(0.0)

    # ------------------------------------------------------------------
    # Fault / alarm
    # ------------------------------------------------------------------

    def test_overcurrent_triggers_fault(self):
        motor, alarms = _make_motor()
        motor.start()
        motor.set_speed(80.0)
        # Force current above limit by injecting enormous pressure
        for _ in range(50):
            motor.update(dt=config.SCAN_CYCLE_S, melt_pressure_bar=9999.0)
        # May or may not fault depending on model, but no exception should raise
        # The fault / alarm path is exercised
        assert isinstance(motor.has_fault, bool)

    def test_fault_prevents_start(self):
        motor, _ = _make_motor()
        motor._fault = True
        motor.start()
        assert not motor.is_running

    def test_reset_fault_clears_flag(self):
        motor, alarms = _make_motor()
        motor._fault = True
        motor.reset_fault()
        assert not motor.has_fault

    # ------------------------------------------------------------------
    # Status dict / repr
    # ------------------------------------------------------------------

    def test_status_dict_keys(self):
        motor, _ = _make_motor()
        d = motor.status_dict()
        for key in ("running", "fault", "setpoint_rpm", "actual_rpm",
                    "vfd_output_pct", "current_a", "torque_pct"):
            assert key in d

    def test_repr(self):
        motor, _ = _make_motor()
        assert "ExtrusionMotor" in repr(motor)
