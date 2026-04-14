(*
    Generic extrusion-motor/VFD function block for IEC 61131-3 Structured Text.

    Handles:
    - speed reference command
    - estimated load / current supervision
    - overspeed and overcurrent interlocks
*)

FUNCTION_BLOCK FB_ExtrusionMotor
VAR_INPUT
    RunCmd : BOOL;
    ResetCmd : BOOL;
    SpeedSetpointRpm : REAL := 80.0;
    ActualRpmPV : REAL;
    MeltPressureBar : REAL;
    MinRpm : REAL := 5.0;
    MaxRpm : REAL := 150.0;
    RatedCurrentA : REAL := 100.0;
    CurrentLimitA : REAL := 100.0;
    MaxTorquePct : REAL := 120.0;
    DieMaxPressureBar : REAL := 350.0;
    BackpressureCoef : REAL := 0.6;
    Kp : REAL := 1.5;
END_VAR
VAR_OUTPUT
    MotorEnable : BOOL := FALSE;
    SpeedCommandRpm : REAL := 5.0;
    VfdOutputPct : REAL := 0.0;
    TorquePct : REAL := 0.0;
    CurrentEstimateA : REAL := 0.0;
    OverCurrentAlarm : BOOL := FALSE;
    OverSpeedAlarm : BOOL := FALSE;
    StallWarning : BOOL := FALSE;
    FaultActive : BOOL := FALSE;
END_VAR
VAR
    SpeedError : REAL := 0.0;
    SpeedLoadPct : REAL := 0.0;
    PressureLoadPct : REAL := 0.0;
END_VAR

IF ResetCmd THEN
    OverCurrentAlarm := FALSE;
    OverSpeedAlarm := FALSE;
    StallWarning := FALSE;
    FaultActive := FALSE;
END_IF;

SpeedCommandRpm := LIMIT(MinRpm, SpeedSetpointRpm, MaxRpm);

IF RunCmd AND NOT FaultActive THEN
    MotorEnable := TRUE;
    SpeedError := SpeedCommandRpm - ActualRpmPV;
    VfdOutputPct := LIMIT(0.0, SpeedError * Kp, 100.0);
ELSE
    MotorEnable := FALSE;
    VfdOutputPct := 0.0;
END_IF;

IF MaxRpm > 0.0 THEN
    SpeedLoadPct := (ActualRpmPV / MaxRpm) * 40.0;
ELSE
    SpeedLoadPct := 0.0;
END_IF;

IF DieMaxPressureBar > 0.0 THEN
    PressureLoadPct := (MeltPressureBar / DieMaxPressureBar) * 60.0;
ELSE
    PressureLoadPct := 0.0;
END_IF;

TorquePct := LIMIT(0.0, SpeedLoadPct + (PressureLoadPct * BackpressureCoef), 100.0);
CurrentEstimateA := (TorquePct / 100.0) * RatedCurrentA;

OverCurrentAlarm := CurrentEstimateA >= CurrentLimitA;
OverSpeedAlarm := ActualRpmPV > (MaxRpm * 1.05);
StallWarning := TorquePct >= MaxTorquePct;

IF OverCurrentAlarm OR OverSpeedAlarm THEN
    FaultActive := TRUE;
END_IF;

END_FUNCTION_BLOCK
