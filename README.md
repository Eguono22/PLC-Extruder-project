# PLC Extruder Project

Industrial extruder operation platform that automates the complete extrusion
process—from material feeding and barrel heating to melting, mixing, and
shaping—while ensuring precise control, safety, and consistent product quality.

---

## Overview

This repository implements a software model of a PLC-controlled industrial
extruder.  The platform covers every stage of the extrusion process:

| Stage | Component |
|---|---|
| Material feeding | `MaterialFeeder` – gravimetric hopper feed with PID rate control |
| Barrel heating | `BarrelHeater` – multi-zone temperature control (PID + cooling) |
| Melting & mixing | `ExtrusionMotor` – VFD-controlled screw drive |
| Shaping | `DieZone` – die temperature, melt-pressure, and throughput monitoring |
| Safety | `SafetySystem` – interlocks, E-Stop, watchdog |
| Orchestration | `ExtruderController` – state machine tying all sub-systems together |

---

## Architecture

```
PLC-Extruder-project/
├── config.py                      # Process parameters & safety limits
├── main.py                        # CLI entry point / demo simulation
├── requirements.txt
├── plc_extruder/
│   ├── controller.py              # State machine: IDLE → STARTUP → RUNNING → SHUTDOWN
│   ├── components/
│   │   ├── feeder.py              # Material feeder (hopper, auger, PID)
│   │   ├── heater.py              # Multi-zone barrel heater
│   │   ├── motor.py               # Extrusion screw motor / VFD
│   │   ├── die.py                 # Die zone (temperature + melt pressure)
│   │   └── safety.py             # Safety interlocks & emergency stop
│   └── utils/
│       ├── pid.py                 # Discrete PID with anti-windup
│       └── alarms.py              # Alarm log and severity management
└── tests/
    ├── test_pid.py
    ├── test_alarms.py
    ├── test_feeder.py
    ├── test_heater.py
    ├── test_motor.py
    ├── test_safety.py
    └── test_controller.py
```

---

## Controller State Machine

```
IDLE ──start()──► STARTUP ──zones at setpoint──► RUNNING
                                                     │
                                               stop()│
                                                     ▼
                                            SHUTDOWN ──motor stopped──► IDLE

Any state ──safety fault / E-Stop──► EMERGENCY_STOP ──reset()──► IDLE
```

---

## Quick Start

**Requirements:** Python >= 3.8 (no external packages needed).

### Run the demo simulation

```bash
python main.py
```

Or customise the recipe:

```bash
python main.py --run-time 300 --feed-rate 60 --screw-rpm 90 --status-interval 500
```

### Use the API directly

```python
from plc_extruder import ExtruderController

ctrl = ExtruderController()
ctrl.set_recipe(feed_rate=50.0, screw_rpm=80.0)
ctrl.start()

for _ in range(30_000):          # simulate 3000 s at 100 ms scan cycle
    state = ctrl.scan()
    if state.name == "RUNNING":
        break

print(ctrl.format_status())
ctrl.stop()
```

### Run the tests

```bash
python -m pytest tests/ -v
```

---

## PLC Structured Text

A vendor-neutral IEC 61131-3 Structured Text version of the top-level
controller state machine is available at `plc/ExtruderController.st`.

It translates the orchestration logic from `plc_extruder/controller.py`
into a PLC-friendly function block:

- `FB_ExtruderController` manages `IDLE`, `STARTUP`, `RUNNING`,
  `SHUTDOWN`, and `EMERGENCY_STOP`
- recipe setpoints are clamped and exposed as maintained outputs
- start, stop, reset, and emergency stop commands are handled as
  edge-triggered operator inputs
- heater, die, feeder, and motor control are exposed as PLC outputs so
  they can be wired to separate function blocks or real I/O

This file is intentionally generic so it can be adapted for platforms
such as Siemens TIA Portal, CODESYS, Beckhoff TwinCAT, or Rockwell
Structured Text with only minor syntax adjustments.

Additional PLC blocks are also provided:

- `plc/FB_HeatingZone.st`
- `plc/FB_DieZone.st`
- `plc/FB_MaterialFeeder.st`
- `plc/FB_ExtrusionMotor.st`
- `plc/FB_SafetySystem.st`
- `plc/ExtruderCellExample.st`

Together these give you a full PLC-oriented baseline that mirrors the
Python architecture: component function blocks plus a top-level
sequencing controller.

For Beckhoff specifically, there is now a TwinCAT-oriented set of files
under `plc/twincat/`, including strict DUT enums, a global config list,
an `R_TRIG`-based controller, and a TwinCAT wiring example program.

---

## Key Design Decisions

### PID Controller (`plc_extruder/utils/pid.py`)
Standard discrete PID with **clamping anti-windup**: when the output saturates,
the integral term is back-calculated to prevent wind-up.  Used for temperature
zones, screw speed, and feed rate control.

### Alarm System (`plc_extruder/utils/alarms.py`)
A centralised `AlarmManager` keeps an ordered log of all raised alarms.  Each
alarm has a severity level (`INFO → WARNING → FAULT → CRITICAL`) and can be
individually acknowledged.  Alarms remain in the historical log after being
cleared.

### Safety System (`plc_extruder/components/safety.py`)
Evaluated on **every scan cycle** before normal process logic:

- Hardware E-Stop button
- Software-initiated E-Stop
- Over-temperature interlock (any barrel zone >= `MAX_BARREL_TEMP`)
- Die over-pressure interlock (>= `DIE_MAX_PRESSURE`)
- Motor over-current / fault interlock
- PLC watchdog (scan-cycle stall detection)

### Configuration (`config.py`)
All process parameters (setpoints, safety limits, PID gains, scan cycle) are
centralised in `config.py` for easy tuning without modifying source code.
