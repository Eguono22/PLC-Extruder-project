(*
    Generic safety/interlock function block for IEC 61131-3 Structured Text.

    This block consolidates:
    - hardware and software E-stop
    - temperature / pressure / drive-fault interlocks
    - watchdog supervision input from a higher-level task
*)

TYPE E_SafetyState :
(
    SAFE,
    WARNING,
    E_STOP
);
END_TYPE


FUNCTION_BLOCK FB_SafetySystem
VAR_INPUT
    ResetCmd : BOOL;
    HardwareEStop : BOOL;
    SoftwareEStop : BOOL;
    AnyZoneOverTemp : BOOL;
    DieOverPressure : BOOL;
    MotorFault : BOOL;
    WarningPresent : BOOL;
    WatchdogHealthy : BOOL := TRUE;
END_VAR
VAR_OUTPUT
    State : E_SafetyState := SAFE;
    EStopActive : BOOL := FALSE;
    InterlockTempAlarm : BOOL := FALSE;
    InterlockPressureAlarm : BOOL := FALSE;
    InterlockMotorAlarm : BOOL := FALSE;
    WatchdogAlarm : BOOL := FALSE;
END_VAR

IF ResetCmd THEN
    InterlockTempAlarm := FALSE;
    InterlockPressureAlarm := FALSE;
    InterlockMotorAlarm := FALSE;
    WatchdogAlarm := FALSE;
    EStopActive := FALSE;
    State := SAFE;
END_IF;

IF AnyZoneOverTemp THEN
    InterlockTempAlarm := TRUE;
END_IF;

IF DieOverPressure THEN
    InterlockPressureAlarm := TRUE;
END_IF;

IF MotorFault THEN
    InterlockMotorAlarm := TRUE;
END_IF;

IF NOT WatchdogHealthy THEN
    WatchdogAlarm := TRUE;
END_IF;

EStopActive :=
    HardwareEStop OR
    SoftwareEStop OR
    InterlockTempAlarm OR
    InterlockPressureAlarm OR
    InterlockMotorAlarm OR
    WatchdogAlarm;

IF EStopActive THEN
    State := E_STOP;
ELSIF WarningPresent THEN
    State := WARNING;
ELSE
    State := SAFE;
END_IF;

END_FUNCTION_BLOCK
