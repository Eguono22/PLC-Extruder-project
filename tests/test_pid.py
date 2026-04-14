"""Unit tests for the PID controller."""

import pytest
from plc_extruder.utils.pid import PIDController


class TestPIDController:
    def _make(self, **kwargs) -> PIDController:
        defaults = dict(kp=2.0, ki=0.5, kd=0.1, output_min=0.0, output_max=100.0)
        defaults.update(kwargs)
        return PIDController(**defaults)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_default_state(self):
        pid = self._make()
        assert pid.last_output == 0.0

    def test_invalid_bounds_raises(self):
        with pytest.raises(ValueError):
            PIDController(kp=1.0, ki=0.0, kd=0.0, output_min=100.0, output_max=0.0)

    def test_equal_bounds_raises(self):
        with pytest.raises(ValueError):
            PIDController(kp=1.0, ki=0.0, kd=0.0, output_min=50.0, output_max=50.0)

    # ------------------------------------------------------------------
    # Basic behaviour
    # ------------------------------------------------------------------

    def test_positive_error_produces_positive_output(self):
        pid = self._make(ki=0.0, kd=0.0)  # pure P only
        out = pid.compute(setpoint=100.0, process_value=50.0, dt=0.1)
        assert out > 0.0

    def test_zero_error_produces_zero_p_output(self):
        pid = self._make(kp=2.0, ki=0.0, kd=0.0)
        out = pid.compute(setpoint=50.0, process_value=50.0, dt=0.1)
        assert out == pytest.approx(0.0, abs=1e-9)

    def test_output_clamped_at_max(self):
        pid = self._make(kp=100.0, ki=0.0, kd=0.0)
        out = pid.compute(setpoint=100.0, process_value=0.0, dt=0.1)
        assert out <= 100.0

    def test_output_clamped_at_min(self):
        pid = self._make(kp=100.0, ki=0.0, kd=0.0)
        out = pid.compute(setpoint=0.0, process_value=100.0, dt=0.1)
        assert out >= 0.0

    # ------------------------------------------------------------------
    # Integral behaviour
    # ------------------------------------------------------------------

    def test_integral_accumulates(self):
        pid = self._make(kp=0.0, ki=1.0, kd=0.0)
        out1 = pid.compute(setpoint=10.0, process_value=0.0, dt=1.0)
        out2 = pid.compute(setpoint=10.0, process_value=0.0, dt=1.0)
        assert out2 > out1

    def test_anti_windup_prevents_integral_blow_up(self):
        pid = self._make(kp=0.0, ki=1.0, kd=0.0, output_max=50.0)
        for _ in range(1000):
            pid.compute(setpoint=100.0, process_value=0.0, dt=1.0)
        assert pid.last_output <= 50.0

    # ------------------------------------------------------------------
    # Zero / edge cases
    # ------------------------------------------------------------------

    def test_zero_dt_returns_last_output(self):
        pid = self._make()
        pid.compute(setpoint=50.0, process_value=30.0, dt=0.1)
        last = pid.last_output
        out = pid.compute(setpoint=50.0, process_value=30.0, dt=0.0)
        assert out == last

    def test_reset_clears_state(self):
        pid = self._make()
        pid.compute(setpoint=100.0, process_value=0.0, dt=0.1)
        pid.reset()
        assert pid.last_output == 0.0

    def test_repr(self):
        pid = self._make()
        assert "PIDController" in repr(pid)

    # ------------------------------------------------------------------
    # Convergence
    # ------------------------------------------------------------------

    def test_converges_on_setpoint(self):
        """With a fixed P setpoint, PID should drive error close to zero."""
        pid = self._make(kp=3.0, ki=0.5, kd=0.1)
        pv = 20.0
        sp = 200.0
        dt = 0.1
        for _ in range(5000):
            output = pid.compute(setpoint=sp, process_value=pv, dt=dt)
            # Simple first-order plant: dPV/dt ≈ output * 0.5 - ambient_loss
            pv += (output * 0.5 - (pv - 20.0) * 0.05) * dt
        assert abs(pv - sp) < 10.0, f"PV did not converge: {pv:.1f}"
