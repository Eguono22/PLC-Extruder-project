# TwinCAT Mapping

This folder contains Beckhoff TwinCAT-oriented Structured Text assets for the
extruder project.

Files:

- `DUT_ExtruderApp.st`: machine modes, recipe IDs, recipe structure, permissives, alarm summary
- `DUT_ControllerState.st`: strict qualified controller-state enum
- `DUT_SafetyState.st`: strict qualified safety-state enum
- `DUT_ExtruderIo.st`: HMI, I/O, and status structures
- `GVL_ExtruderConfig.st`: global constants for recipe and safety tuning
- `GVL_ExtruderIo.st`: global command, I/O, output, and status tags
- `GVL_ExtruderRecipes.st`: built-in product recipes
- `FB_RecipeManager_Tc.st`: selects default, HDPE, PVC, or custom recipes
- `FB_AlarmManager_Tc.st`: aggregates warnings, faults, and criticals into a summary word
- `FB_ExtruderController_Tc.st`: TwinCAT sequencer using `R_TRIG`
- `PRG_ExtruderCell_Tc.st`: example top-level program wiring the controller to the component FBs

Recommended TwinCAT project layout:

1. Add the DUT files under `DUTs`
2. Add the GVL files under `GVLs`
3. Add `FB_ExtruderController_Tc.st` under `POUs`
4. Import the generic component blocks from the parent `plc/` folder or replace them with your production FBs
5. Add `PRG_ExtruderCell_Tc.st` as the main program or as a template for your task program

Notes:

- `R_TRIG` comes from the TwinCAT standard library
- the TwinCAT controller uses `LREAL`/`UDINT` and strict enum qualification
- `gExtruderCmd`, `gExtruderAI`, `gExtruderDI`, `gExtruderAO`, `gExtruderDO`, and `gExtruderStatus` are intended to be the stable tag surface for HMI and I/O mapping
- the application now includes machine mode handling, permissives, recipe selection, and alarm summarisation around the core sequencer
- map analog and digital terminals against the fields in `GVL_ExtruderIo.st` instead of scattering raw I/O variables through your logic
- the generic component FBs in `plc/` are still useful as a starting point, but for production you may want TwinCAT PID, alarms, and hardware abstraction around EtherCAT I/O

Suggested task split:

1. A cyclic control task at `100 ms` for `PRG_ExtruderCell_Tc`
2. A faster I/O task for terminal updates if your project architecture uses one
3. An HMI or ADS-facing layer that reads and writes only the `gExtruder*` structures

Suggested first physical mapping:

1. Map thermocouple inputs to `gExtruderAI.Zone*Temp_C` and `gExtruderAI.DieTemp_C`
2. Map VFD feedback to `gExtruderAI.MotorRpm` and `gExtruderAI.MotorCurrent_A`
3. Map feeder scale or inferred flow to `gExtruderAI.FeederRateKgH`
4. Map hopper level instrumentation to `gExtruderAI.HopperLevelPct`
5. Map permissives and safety contacts to `gExtruderDI`
6. Map heater, feeder, motor, and stacklight commands from `gExtruderDO` and `gExtruderAO`
