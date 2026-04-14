"""Integration tests for the ExtruderController state machine."""

import pytest
from plc_extruder.controller import ExtruderController, ControllerState
import config


def _make_ctrl(**kwargs) -> ExtruderController:
    return ExtruderController(**kwargs)


class TestControllerStateTransitions:

    def test_initial_state_is_idle(self):
        ctrl = _make_ctrl()
        assert ctrl.state == ControllerState.IDLE

    def test_start_transitions_to_startup(self):
        ctrl = _make_ctrl()
        result = ctrl.start()
        assert result is True
        assert ctrl.state == ControllerState.STARTUP

    def test_start_rejected_if_already_running(self):
        ctrl = _make_ctrl()
        ctrl.start()
        result = ctrl.start()
        assert result is False

    def test_stop_transitions_to_shutdown(self):
        ctrl = _make_ctrl()
        ctrl.start()
        result = ctrl.stop()
        assert result is True
        assert ctrl.state == ControllerState.SHUTDOWN

    def test_stop_rejected_when_idle(self):
        ctrl = _make_ctrl()
        result = ctrl.stop()
        assert result is False

    def test_emergency_stop_transitions_to_estop(self):
        ctrl = _make_ctrl()
        ctrl.start()
        ctrl.emergency_stop()
        assert ctrl.state == ControllerState.EMERGENCY_STOP

    def test_reset_from_estop_returns_idle(self):
        ctrl = _make_ctrl()
        ctrl.emergency_stop()
        result = ctrl.reset()
        assert result is True
        assert ctrl.state == ControllerState.IDLE

    def test_reset_from_idle_is_accepted(self):
        ctrl = _make_ctrl()
        result = ctrl.reset()
        assert result is True

    def test_reset_not_accepted_from_startup(self):
        ctrl = _make_ctrl()
        ctrl.start()
        result = ctrl.reset()
        assert result is False


class TestControllerStartupToRunning:

    def _run_to_running(
        self, feed_rate: float = 50.0, screw_rpm: float = 80.0, max_scans: int = 30000
    ) -> ExtruderController:
        ctrl = _make_ctrl()
        ctrl.set_recipe(feed_rate=feed_rate, screw_rpm=screw_rpm)
        ctrl.start()
        for _ in range(max_scans):
            ctrl.scan()
            if ctrl.state == ControllerState.RUNNING:
                break
        return ctrl

    def test_reaches_running_state(self):
        ctrl = self._run_to_running()
        assert ctrl.state == ControllerState.RUNNING

    def test_heater_zones_at_setpoint_in_running(self):
        ctrl = self._run_to_running()
        assert ctrl.heater.all_at_setpoint

    def test_die_at_setpoint_in_running(self):
        ctrl = self._run_to_running()
        assert ctrl.die.at_setpoint

    def test_scan_counter_increments(self):
        ctrl = _make_ctrl()
        ctrl.start()
        for _ in range(10):
            ctrl.scan()
        assert ctrl.scan_number == 10

    def test_run_time_increments_only_in_running(self):
        ctrl = self._run_to_running()
        before = ctrl.run_time_s
        ctrl.scan()
        ctrl.scan()
        assert ctrl.run_time_s > before


class TestControllerRunningToShutdown:

    def _run_to_running(self, max_scans: int = 30000) -> ExtruderController:
        ctrl = _make_ctrl()
        ctrl.set_recipe(feed_rate=50.0, screw_rpm=80.0)
        ctrl.start()
        for _ in range(max_scans):
            ctrl.scan()
            if ctrl.state == ControllerState.RUNNING:
                break
        return ctrl

    def test_shutdown_completes_to_idle(self):
        ctrl = self._run_to_running()
        ctrl.stop()
        for _ in range(10000):
            ctrl.scan()
            if ctrl.state == ControllerState.IDLE:
                break
        assert ctrl.state == ControllerState.IDLE

    def test_motor_stops_after_shutdown(self):
        ctrl = self._run_to_running()
        ctrl.stop()
        for _ in range(10000):
            ctrl.scan()
            if ctrl.state == ControllerState.IDLE:
                break
        assert ctrl.motor.actual_rpm < 1.0

    def test_start_resets_run_time_for_new_cycle(self):
        ctrl = self._run_to_running()
        ctrl.scan()
        assert ctrl.run_time_s > 0.0
        ctrl.stop()
        for _ in range(10000):
            ctrl.scan()
            if ctrl.state == ControllerState.IDLE:
                break
        ctrl.start()
        assert ctrl.run_time_s == pytest.approx(0.0)


class TestControllerSafety:

    def test_safety_estop_stops_from_running(self):
        ctrl = _make_ctrl()
        ctrl.set_recipe(feed_rate=50.0, screw_rpm=80.0)
        ctrl.start()
        for _ in range(30000):
            ctrl.scan()
            if ctrl.state == ControllerState.RUNNING:
                break
        ctrl.safety.trigger_estop_hardware()
        ctrl.scan()
        assert ctrl.state == ControllerState.EMERGENCY_STOP

    def test_over_temp_triggers_estop_during_run(self):
        ctrl = _make_ctrl()
        ctrl.start()
        # Force a zone to critical temperature
        ctrl.heater.zones[0]._temperature = config.MAX_BARREL_TEMP + 10.0
        ctrl.scan()
        assert ctrl.state == ControllerState.EMERGENCY_STOP


class TestRecipeUpdate:

    def test_set_recipe_updates_setpoints(self):
        ctrl = _make_ctrl()
        ctrl.set_recipe(feed_rate=70.0, screw_rpm=100.0)
        assert ctrl._recipe_feed_rate == pytest.approx(70.0)
        assert ctrl._recipe_screw_rpm == pytest.approx(100.0)

    def test_set_recipe_clamped_to_limits(self):
        ctrl = _make_ctrl()
        ctrl.set_recipe(feed_rate=0.0, screw_rpm=9999.0)
        assert ctrl._recipe_feed_rate >= config.FEEDER_MIN_RATE
        assert ctrl._recipe_screw_rpm <= config.MOTOR_MAX_RPM


class TestControllerStatus:

    def test_status_dict_keys(self):
        ctrl = _make_ctrl()
        d = ctrl.status_dict()
        for key in ("state", "scan_number", "run_time_s", "recipe",
                    "safety", "alarms", "heater", "motor", "feeder", "die"):
            assert key in d

    def test_format_status_returns_string(self):
        ctrl = _make_ctrl()
        s = ctrl.format_status()
        assert isinstance(s, str)
        assert len(s) > 0

    def test_repr(self):
        ctrl = _make_ctrl()
        assert "ExtruderController" in repr(ctrl)
