# TwinCAT Mapping

This folder contains Beckhoff TwinCAT-oriented Structured Text assets for the
extruder project.

Files:

- `DUT_ControllerState.st`: strict qualified controller-state enum
- `DUT_SafetyState.st`: strict qualified safety-state enum
- `GVL_ExtruderConfig.st`: global constants for recipe and safety tuning
- `FB_ExtruderController_Tc.st`: TwinCAT sequencer using `R_TRIG`
- `PRG_ExtruderCell_Tc.st`: example top-level program wiring the controller to the component FBs

Recommended TwinCAT project layout:

1. Add the DUT files under `DUTs`
2. Add `GVL_ExtruderConfig.st` under `GVLs`
3. Add `FB_ExtruderController_Tc.st` under `POUs`
4. Import the generic component blocks from the parent `plc/` folder or replace them with your production FBs
5. Add `PRG_ExtruderCell_Tc.st` as the main program or as a template for your task program

Notes:

- `R_TRIG` comes from the TwinCAT standard library
- the TwinCAT controller uses `LREAL`/`UDINT` and strict enum qualification
- the generic component FBs in `plc/` are still useful as a starting point, but for production you may want TwinCAT PID, alarms, and hardware abstraction around EtherCAT I/O
