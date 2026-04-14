(*
    Generic heating-zone function block for IEC 61131-3 Structured Text.

    Intended use:
    - One instance per barrel zone
    - Real PLC input should be the measured process temperature
    - Real PLC output should drive heater SSR/contactors and cooling valve/fan

    Note:
    - This uses a simple proportional control law as a portable baseline.
    - Replace the proportional section with your platform's PID block if needed.
*)

FUNCTION_BLOCK FB_HeatingZone
VAR_INPUT
    EnableCmd : BOOL;
    ResetCmd : BOOL;
    TemperaturePV : REAL;
    Setpoint : REAL := 200.0;
    TempTolerance : REAL := 5.0;
    MaxTemp : REAL := 280.0;
    UnderTempBand : REAL := 20.0;
    Kp : REAL := 3.0;
END_VAR
VAR_OUTPUT
    HeaterEnable : BOOL := FALSE;
    HeaterOutputPct : REAL := 0.0;
    CoolingOutputPct : REAL := 0.0;
    AtSetpoint : BOOL := FALSE;
    OverTempAlarm : BOOL := FALSE;
    UnderTempAlarm : BOOL := FALSE;
END_VAR
VAR
    TempError : REAL := 0.0;
END_VAR

IF ResetCmd THEN
    OverTempAlarm := FALSE;
    UnderTempAlarm := FALSE;
END_IF;

HeaterEnable := EnableCmd;
AtSetpoint := ABS(TemperaturePV - Setpoint) <= TempTolerance;

IF NOT EnableCmd THEN
    HeaterOutputPct := 0.0;
    CoolingOutputPct := 0.0;
ELSIF TemperaturePV >= MaxTemp THEN
    OverTempAlarm := TRUE;
    HeaterOutputPct := 0.0;
    CoolingOutputPct := 100.0;
ELSE
    TempError := Setpoint - TemperaturePV;
    HeaterOutputPct := LIMIT(0.0, TempError * Kp, 100.0);

    IF TempError < (-1.0 * TempTolerance) THEN
        CoolingOutputPct := LIMIT(0.0, ABS(TempError) * 5.0, 100.0);
    ELSE
        CoolingOutputPct := 0.0;
    END_IF;

    IF TemperaturePV < (Setpoint - UnderTempBand) THEN
        UnderTempAlarm := TRUE;
    ELSE
        UnderTempAlarm := FALSE;
    END_IF;
END_IF;

END_FUNCTION_BLOCK
