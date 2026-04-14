"""
Discrete PID controller with anti-windup clamping.

The controller is designed for fixed-interval (scan-cycle) execution.
Each call to :meth:`compute` advances the controller by one scan cycle.

Usage example::

    pid = PIDController(kp=2.0, ki=0.5, kd=0.1, output_min=0.0, output_max=100.0)
    output = pid.compute(setpoint=200.0, process_value=185.0, dt=0.1)
"""


class PIDController:
    """Proportional-Integral-Derivative controller with output clamping.

    Anti-windup is achieved by back-calculating the integral term whenever
    the output saturates (clamping anti-windup).

    Args:
        kp: Proportional gain.
        ki: Integral gain.
        kd: Derivative gain.
        output_min: Lower bound for the controller output.
        output_max: Upper bound for the controller output.
    """

    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        output_min: float = 0.0,
        output_max: float = 100.0,
    ) -> None:
        if output_min >= output_max:
            raise ValueError("output_min must be less than output_max")
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max

        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._last_output: float = 0.0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def compute(self, setpoint: float, process_value: float, dt: float) -> float:
        """Compute one PID iteration.

        Args:
            setpoint: Desired value.
            process_value: Current measured value.
            dt: Time elapsed since the last call (seconds).

        Returns:
            Controller output clamped to [output_min, output_max].
        """
        if dt <= 0:
            return self._last_output

        error = setpoint - process_value

        # Proportional term
        p_term = self.kp * error

        # Integral term with anti-windup back-calculation
        self._integral += error * dt
        i_term = self.ki * self._integral

        # Derivative term (on error, not PV, to avoid derivative kick)
        derivative = (error - self._prev_error) / dt
        d_term = self.kd * derivative

        raw_output = p_term + i_term + d_term
        output = max(self.output_min, min(self.output_max, raw_output))

        # Anti-windup: unwind integral if output is saturated
        if raw_output != output and self.ki != 0:
            self._integral -= (raw_output - output) / self.ki

        self._prev_error = error
        self._last_output = output
        return output

    def reset(self) -> None:
        """Reset internal state (use when controller is re-enabled)."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_output = 0.0

    @property
    def last_output(self) -> float:
        """Return the most recent controller output without recomputing."""
        return self._last_output

    def __repr__(self) -> str:
        return (
            f"PIDController(kp={self.kp}, ki={self.ki}, kd={self.kd}, "
            f"output=[{self.output_min}, {self.output_max}])"
        )
