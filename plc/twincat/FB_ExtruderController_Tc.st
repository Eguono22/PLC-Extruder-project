(*
    Beckhoff TwinCAT-oriented controller sequencer.

    TwinCAT details:
    - uses LREAL/UDINT
    - uses Standard library R_TRIG instances for edge detection
    - uses qualified enum names with strict typing
*)

FUNCTION_BLOCK FB_ExtruderController_Tc
VAR_INPUT
    StartCmd : BOOL;
    StopCmd : BOOL;
    ResetCmd : BOOL;
    EmergencyStopCmd : BOOL;

    SafetyEStop : BOOL;
    HeaterAllAtSetpoint : BOOL;
    DieAtSetpoint : BOOL;
    MotorActualRpm : LREAL;

    RecipeFeedRateCmd : LREAL := 50.0;
    RecipeScrewRpmCmd : LREAL := 80.0;
    FeedRateMin : LREAL := GVL_ExtruderConfig.cFeedMinKgH;
    FeedRateMax : LREAL := GVL_ExtruderConfig.cFeedMaxKgH;
    ScrewRpmMin : LREAL := GVL_ExtruderConfig.cMotorMinRpm;
    ScrewRpmMax : LREAL := GVL_ExtruderConfig.cMotorMaxRpm;
    CycleTime_s : LREAL := GVL_ExtruderConfig.cCycleTime_s;
END_VAR
VAR_OUTPUT
    State : E_ControllerState_Tc := E_ControllerState_Tc.IDLE;
    ScanNumber : UDINT := 0;
    RunTime_s : LREAL := 0.0;

    FeedRateSetpoint : LREAL := GVL_ExtruderConfig.cFeedMinKgH;
    ScrewRpmSetpoint : LREAL := GVL_ExtruderConfig.cMotorMinRpm;

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
    PrevState : E_ControllerState_Tc := E_ControllerState_Tc.IDLE;
    rtStart : R_TRIG;
    rtStop : R_TRIG;
    rtReset : R_TRIG;
    rtEmergency : R_TRIG;
END_VAR

rtStart(CLK := StartCmd);
rtStop(CLK := StopCmd);
rtReset(CLK := ResetCmd);
rtEmergency(CLK := EmergencyStopCmd);

ResetSafetyCmd := FALSE;
ResetMotorFaultCmd := FALSE;
ResetFeederFaultCmd := FALSE;
RaiseShutdownAlarmCmd := FALSE;
ClearShutdownAlarmCmd := FALSE;
RaiseEStopAlarmCmd := FALSE;

ScanNumber := ScanNumber + 1;

FeedRateSetpoint := MAX(FeedRateMin, MIN(RecipeFeedRateCmd, FeedRateMax));
ScrewRpmSetpoint := MAX(ScrewRpmMin, MIN(RecipeScrewRpmCmd, ScrewRpmMax));

IF ((SafetyEStop OR rtEmergency.Q) AND
    (State <> E_ControllerState_Tc.EMERGENCY_STOP) AND
    (State <> E_ControllerState_Tc.IDLE)) THEN
    State := E_ControllerState_Tc.EMERGENCY_STOP;
END_IF;

CASE State OF
    E_ControllerState_Tc.IDLE:
        IF rtStart.Q THEN
            RunTime_s := 0.0;
            State := E_ControllerState_Tc.STARTUP;
        ELSIF rtReset.Q THEN
            RunTime_s := 0.0;
            ResetSafetyCmd := TRUE;
            ResetMotorFaultCmd := TRUE;
            ResetFeederFaultCmd := TRUE;
        END_IF;

    E_ControllerState_Tc.STARTUP:
        IF rtStop.Q THEN
            State := E_ControllerState_Tc.SHUTDOWN;
        ELSIF HeaterAllAtSetpoint AND DieAtSetpoint THEN
            State := E_ControllerState_Tc.RUNNING;
        END_IF;

    E_ControllerState_Tc.RUNNING:
        IF rtStop.Q THEN
            State := E_ControllerState_Tc.SHUTDOWN;
        ELSIF SafetyEStop OR rtEmergency.Q THEN
            State := E_ControllerState_Tc.EMERGENCY_STOP;
        ELSE
            RunTime_s := RunTime_s + CycleTime_s;
        END_IF;

    E_ControllerState_Tc.SHUTDOWN:
        IF SafetyEStop OR rtEmergency.Q THEN
            State := E_ControllerState_Tc.EMERGENCY_STOP;
        ELSIF MotorActualRpm < 0.5 THEN
            State := E_ControllerState_Tc.IDLE;
            ClearShutdownAlarmCmd := TRUE;
        END_IF;

    E_ControllerState_Tc.EMERGENCY_STOP:
        IF rtReset.Q THEN
            RunTime_s := 0.0;
            ResetSafetyCmd := TRUE;
            ResetMotorFaultCmd := TRUE;
            ResetFeederFaultCmd := TRUE;
            ClearShutdownAlarmCmd := TRUE;
            State := E_ControllerState_Tc.IDLE;
        END_IF;
END_CASE;

IF State <> PrevState THEN
    CASE State OF
        E_ControllerState_Tc.STARTUP:
            RunTime_s := 0.0;

        E_ControllerState_Tc.SHUTDOWN:
            RaiseShutdownAlarmCmd := TRUE;

        E_ControllerState_Tc.EMERGENCY_STOP:
            RaiseEStopAlarmCmd := TRUE;
    END_CASE;

    PrevState := State;
END_IF;

HeaterEnableCmd := (State = E_ControllerState_Tc.STARTUP) OR
                   (State = E_ControllerState_Tc.RUNNING) OR
                   (State = E_ControllerState_Tc.SHUTDOWN);
DieEnableCmd := HeaterEnableCmd;
FeederRunCmd := (State = E_ControllerState_Tc.RUNNING);
MotorRunCmd := (State = E_ControllerState_Tc.RUNNING);

END_FUNCTION_BLOCK
