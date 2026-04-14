(*
    Vendor-neutral IEC 61131-3 Structured Text translation of the
    Python ExtruderController state machine.

    Source model:
    - plc_extruder/controller.py

    Notes:
    - This block focuses on orchestration, not detailed process physics.
    - Heater, feeder, motor, die, and safety logic are expected to live
      in separate PLC function blocks.
    - Commands such as StartCmd/StopCmd/ResetCmd are edge-triggered.
    - Maintained outputs are derived from State each scan.
*)

TYPE E_ControllerState :
(
    IDLE,
    STARTUP,
    RUNNING,
    SHUTDOWN,
    EMERGENCY_STOP
);
END_TYPE


FUNCTION_BLOCK FB_ExtruderController
VAR_INPUT
    StartCmd : BOOL;
    StopCmd : BOOL;
    ResetCmd : BOOL;
    EmergencyStopCmd : BOOL;

    SafetyEStop : BOOL;
    HeaterAllAtSetpoint : BOOL;
    DieAtSetpoint : BOOL;
    MotorActualRpm : REAL;

    RecipeFeedRateCmd : REAL := 50.0;
    RecipeScrewRpmCmd : REAL := 80.0;
    FeedRateMin : REAL := 5.0;
    FeedRateMax : REAL := 100.0;
    ScrewRpmMin : REAL := 5.0;
    ScrewRpmMax : REAL := 150.0;

    CycleTime_s : REAL := 0.1;
END_VAR
VAR_OUTPUT
    State : E_ControllerState := IDLE;
    ScanNumber : DINT := 0;
    RunTime_s : REAL := 0.0;

    FeedRateSetpoint : REAL := 5.0;
    ScrewRpmSetpoint : REAL := 5.0;

    HeaterEnableCmd : BOOL := FALSE;
    DieEnableCmd : BOOL := FALSE;
    FeederRunCmd : BOOL := FALSE;
    MotorRunCmd : BOOL := FALSE;

    ResetSafetyCmd : BOOL := FALSE;
    ResetMotorFaultCmd : BOOL := FALSE;
    ResetFeederFaultCmd : BOOL := FALSE;

    RaiseShutdownAlarmCmd : BOOL := FALSE;
    ClearShutdownAlarmCmd : BOOL := FALSE;
    RaiseEStopAlarmCmd : BOOL := FALSE;
END_VAR
VAR
    PrevState : E_ControllerState := IDLE;

    StartCmdPrev : BOOL := FALSE;
    StopCmdPrev : BOOL := FALSE;
    ResetCmdPrev : BOOL := FALSE;
    EmergencyStopCmdPrev : BOOL := FALSE;

    StartEdge : BOOL := FALSE;
    StopEdge : BOOL := FALSE;
    ResetEdge : BOOL := FALSE;
    EmergencyStopEdge : BOOL := FALSE;
END_VAR

(* Reset one-scan pulse outputs *)
ResetSafetyCmd := FALSE;
ResetMotorFaultCmd := FALSE;
ResetFeederFaultCmd := FALSE;
RaiseShutdownAlarmCmd := FALSE;
ClearShutdownAlarmCmd := FALSE;
RaiseEStopAlarmCmd := FALSE;

(* Rising-edge detection *)
StartEdge := StartCmd AND NOT StartCmdPrev;
StopEdge := StopCmd AND NOT StopCmdPrev;
ResetEdge := ResetCmd AND NOT ResetCmdPrev;
EmergencyStopEdge := EmergencyStopCmd AND NOT EmergencyStopCmdPrev;

StartCmdPrev := StartCmd;
StopCmdPrev := StopCmd;
ResetCmdPrev := ResetCmd;
EmergencyStopCmdPrev := EmergencyStopCmd;

(* Scan bookkeeping *)
ScanNumber := ScanNumber + 1;

(* Recipe clamping *)
FeedRateSetpoint := MAX(FeedRateMin, MIN(RecipeFeedRateCmd, FeedRateMax));
ScrewRpmSetpoint := MAX(ScrewRpmMin, MIN(RecipeScrewRpmCmd, ScrewRpmMax));

(* High-priority safety transition *)
IF ((SafetyEStop OR EmergencyStopEdge) AND (State <> EMERGENCY_STOP) AND (State <> IDLE)) THEN
    State := EMERGENCY_STOP;
END_IF;

(* Operator transitions *)
CASE State OF
    IDLE:
        IF StartEdge THEN
            RunTime_s := 0.0;
            State := STARTUP;
        ELSIF ResetEdge THEN
            RunTime_s := 0.0;
            ResetSafetyCmd := TRUE;
            ResetMotorFaultCmd := TRUE;
            ResetFeederFaultCmd := TRUE;
        END_IF;

    STARTUP:
        IF StopEdge THEN
            State := SHUTDOWN;
        ELSIF HeaterAllAtSetpoint AND DieAtSetpoint THEN
            State := RUNNING;
        END_IF;

    RUNNING:
        IF StopEdge THEN
            State := SHUTDOWN;
        ELSIF SafetyEStop OR EmergencyStopEdge THEN
            State := EMERGENCY_STOP;
        ELSE
            RunTime_s := RunTime_s + CycleTime_s;
        END_IF;

    SHUTDOWN:
        IF SafetyEStop OR EmergencyStopEdge THEN
            State := EMERGENCY_STOP;
        ELSIF MotorActualRpm < 0.5 THEN
            State := IDLE;
            ClearShutdownAlarmCmd := TRUE;
        END_IF;

    EMERGENCY_STOP:
        IF ResetEdge THEN
            RunTime_s := 0.0;
            ResetSafetyCmd := TRUE;
            ResetMotorFaultCmd := TRUE;
            ResetFeederFaultCmd := TRUE;
            ClearShutdownAlarmCmd := TRUE;
            State := IDLE;
        END_IF;
END_CASE;

(* State entry actions *)
IF State <> PrevState THEN
    CASE State OF
        STARTUP:
            RunTime_s := 0.0;

        RUNNING:
            (* Recipe setpoints are already exposed as maintained outputs. *)

        SHUTDOWN:
            RaiseShutdownAlarmCmd := TRUE;

        EMERGENCY_STOP:
            RaiseEStopAlarmCmd := TRUE;

        IDLE:
            (* Outputs are handled below as maintained state outputs. *)
    END_CASE;

    PrevState := State;
END_IF;

(* Maintained outputs by state *)
HeaterEnableCmd := (State = STARTUP) OR (State = RUNNING) OR (State = SHUTDOWN);
DieEnableCmd := (State = STARTUP) OR (State = RUNNING) OR (State = SHUTDOWN);
FeederRunCmd := (State = RUNNING);
MotorRunCmd := (State = RUNNING);

END_FUNCTION_BLOCK
