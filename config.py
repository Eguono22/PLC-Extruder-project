"""
Configuration constants for the PLC Extruder system.

All physical units follow SI conventions unless noted in the comment.
"""

# ---------------------------------------------------------------------------
# Barrel heating zones
# ---------------------------------------------------------------------------
BARREL_ZONE_COUNT = 4
# Setpoints (°C) for zones 1 → 4 (feed zone → metering zone)
BARREL_ZONE_SETPOINTS = [180.0, 200.0, 220.0, 230.0]
# ±°C band that is considered "at setpoint"
TEMP_TOLERANCE = 5.0

# ---------------------------------------------------------------------------
# Die / head zone
# ---------------------------------------------------------------------------
DIE_ZONE_SETPOINT = 235.0      # °C
DIE_TEMP_TOLERANCE = 5.0       # °C
DIE_MAX_PRESSURE = 350.0       # bar  – absolute upper safety limit
DIE_PRESSURE_WARNING = 300.0   # bar  – warning threshold

# ---------------------------------------------------------------------------
# Safety limits
# ---------------------------------------------------------------------------
MAX_BARREL_TEMP = 280.0        # °C  – triggers emergency stop
MIN_BARREL_TEMP = 20.0         # °C  – ambient floor (sanity check)
MAX_MOTOR_CURRENT = 100.0      # A
MAX_MOTOR_TORQUE = 120.0       # % of rated torque
LOW_MATERIAL_LEVEL = 10.0      # %   – low-material warning threshold
EMPTY_MATERIAL_LEVEL = 2.0     # %   – empty hopper alarm

# ---------------------------------------------------------------------------
# Extrusion screw / motor
# ---------------------------------------------------------------------------
MOTOR_MAX_RPM = 150.0
MOTOR_MIN_RPM = 5.0
SCREW_DIAMETER_MM = 60.0
SCREW_L_D_RATIO = 30            # L/D ratio (dimensionless)

# ---------------------------------------------------------------------------
# Material feeder
# ---------------------------------------------------------------------------
FEEDER_MAX_RATE = 100.0        # kg/h
FEEDER_MIN_RATE = 5.0          # kg/h
FEEDER_HOPPER_CAPACITY = 200.0 # kg

# ---------------------------------------------------------------------------
# PID controller defaults
# ---------------------------------------------------------------------------
# Temperature PID (heating zones)
TEMP_PID_KP = 3.0
TEMP_PID_KI = 0.5
TEMP_PID_KD = 0.2
TEMP_PID_OUTPUT_MIN = 0.0      # 0 % heater power
TEMP_PID_OUTPUT_MAX = 100.0    # 100 % heater power

# Speed PID (motor RPM)
SPEED_PID_KP = 1.5
SPEED_PID_KI = 0.3
SPEED_PID_KD = 0.05
SPEED_PID_OUTPUT_MIN = 0.0
SPEED_PID_OUTPUT_MAX = 100.0   # % of VFD output

# Feed-rate PID
FEED_PID_KP = 2.0
FEED_PID_KI = 0.4
FEED_PID_KD = 0.1

# ---------------------------------------------------------------------------
# PLC scan cycle
# ---------------------------------------------------------------------------
SCAN_CYCLE_S = 0.1             # seconds (100 ms)

# ---------------------------------------------------------------------------
# Startup / shutdown ramp rates
# ---------------------------------------------------------------------------
HEAT_RAMP_RATE = 5.0           # °C per scan cycle (simulated heating rate)
COOL_RAMP_RATE = 2.0           # °C per scan cycle (simulated cooling rate)
MOTOR_RAMP_RATE = 2.0          # RPM per scan cycle
