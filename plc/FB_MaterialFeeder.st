(*
    Generic material-feeder function block for IEC 61131-3 Structured Text.

    Handles:
    - run command and drive reference
    - hopper level alarms
    - empty-hopper fault interlock
*)

FUNCTION_BLOCK FB_MaterialFeeder
VAR_INPUT
    RunCmd : BOOL;
    ResetCmd : BOOL;
    FeedRateSetpointKgH : REAL := 50.0;
    ActualRatePVKgH : REAL;
    HopperLevelPctPV : REAL := 100.0;
    MinRateKgH : REAL := 5.0;
    MaxRateKgH : REAL := 100.0;
    LowLevelPct : REAL := 10.0;
    EmptyLevelPct : REAL := 2.0;
    Kp : REAL := 2.0;
END_VAR
VAR_OUTPUT
    FeederEnable : BOOL := FALSE;
    DriveOutputPct : REAL := 0.0;
    FeedRateCommandKgH : REAL := 5.0;
    LowMaterialAlarm : BOOL := FALSE;
    EmptyHopperAlarm : BOOL := FALSE;
    FaultActive : BOOL := FALSE;
END_VAR
VAR
    RateError : REAL := 0.0;
END_VAR

IF ResetCmd THEN
    EmptyHopperAlarm := FALSE;
    FaultActive := FALSE;
END_IF;

FeedRateCommandKgH := LIMIT(MinRateKgH, FeedRateSetpointKgH, MaxRateKgH);
LowMaterialAlarm := HopperLevelPctPV <= LowLevelPct;

IF HopperLevelPctPV <= EmptyLevelPct THEN
    EmptyHopperAlarm := TRUE;
    FaultActive := TRUE;
END_IF;

IF RunCmd AND NOT FaultActive THEN
    FeederEnable := TRUE;
    RateError := FeedRateCommandKgH - ActualRatePVKgH;
    DriveOutputPct := LIMIT(0.0, RateError * Kp, 100.0);
ELSE
    FeederEnable := FALSE;
    DriveOutputPct := 0.0;
END_IF;

END_FUNCTION_BLOCK
