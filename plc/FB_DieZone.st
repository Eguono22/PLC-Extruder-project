(*
    Generic die-zone function block for IEC 61131-3 Structured Text.

    Handles:
    - die temperature command
    - melt pressure estimation
    - throughput estimation
    - over-temperature and over-pressure alarms
*)

FUNCTION_BLOCK FB_DieZone
VAR_INPUT
    EnableCmd : BOOL;
    ResetCmd : BOOL;
    TemperaturePV : REAL;
    Setpoint : REAL := 235.0;
    TempTolerance : REAL := 5.0;
    MaxTemp : REAL := 280.0;

    ScrewRpmPV : REAL;
    FeedRateActualKgH : REAL;
    MotorMaxRpm : REAL := 150.0;
    DieOpeningPct : REAL := 100.0;
    PressureCoef : REAL := 1.8;
    DieMaxPressureBar : REAL := 350.0;
    DieWarningPressureBar : REAL := 300.0;

    Kp : REAL := 3.0;
END_VAR
VAR_OUTPUT
    HeaterEnable : BOOL := FALSE;
    HeaterOutputPct : REAL := 0.0;
    AtSetpoint : BOOL := FALSE;
    MeltPressureBar : REAL := 0.0;
    ThroughputKgH : REAL := 0.0;
    OverTempAlarm : BOOL := FALSE;
    OverPressureAlarm : BOOL := FALSE;
    HighPressureWarning : BOOL := FALSE;
END_VAR
VAR
    TempError : REAL := 0.0;
    EffectiveOpeningPct : REAL := 100.0;
    ViscosityFactor : REAL := 1.0;
END_VAR

IF ResetCmd THEN
    OverTempAlarm := FALSE;
    OverPressureAlarm := FALSE;
    HighPressureWarning := FALSE;
END_IF;

HeaterEnable := EnableCmd;
AtSetpoint := ABS(TemperaturePV - Setpoint) <= TempTolerance;

IF NOT EnableCmd THEN
    HeaterOutputPct := 0.0;
ELSE
    IF TemperaturePV >= MaxTemp THEN
        OverTempAlarm := TRUE;
        HeaterOutputPct := 0.0;
    ELSE
        TempError := Setpoint - TemperaturePV;
        HeaterOutputPct := LIMIT(0.0, TempError * Kp, 100.0);
    END_IF;
END_IF;

EffectiveOpeningPct := LIMIT(5.0, DieOpeningPct, 100.0);

IF ScrewRpmPV <= 0.0 THEN
    MeltPressureBar := 0.0;
    ThroughputKgH := 0.0;
ELSE
    ViscosityFactor := LIMIT(0.2, 1.0 - ((TemperaturePV - 100.0) / 300.0), 1.0);
    MeltPressureBar := PressureCoef * ScrewRpmPV * ViscosityFactor / (EffectiveOpeningPct / 100.0);
    MeltPressureBar := LIMIT(0.0, MeltPressureBar, DieMaxPressureBar * 1.1);

    IF MotorMaxRpm > 0.0 THEN
        ThroughputKgH := FeedRateActualKgH * (ScrewRpmPV / MotorMaxRpm);
    ELSE
        ThroughputKgH := 0.0;
    END_IF;
END_IF;

OverPressureAlarm := MeltPressureBar >= DieMaxPressureBar;
HighPressureWarning := MeltPressureBar >= DieWarningPressureBar;

END_FUNCTION_BLOCK
