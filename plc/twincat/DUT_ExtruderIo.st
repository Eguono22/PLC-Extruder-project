TYPE ST_ExtruderCommands :
STRUCT
    Start : BOOL;
    Stop : BOOL;
    Reset : BOOL;
    EmergencyStop : BOOL;
    Mode : E_ExtruderMode_Tc;
    RecipeId : E_RecipeId_Tc;
    RecipeFeedRateKgH : LREAL;
    RecipeScrewRpm : LREAL;
    Zone1Setpoint_C : LREAL;
    Zone2Setpoint_C : LREAL;
    Zone3Setpoint_C : LREAL;
    Zone4Setpoint_C : LREAL;
    DieSetpoint_C : LREAL;
END_STRUCT
END_TYPE

TYPE ST_ExtruderDigitalInputs :
STRUCT
    EStopOk : BOOL;
    GuardDoorClosed : BOOL;
    HeaterZone1Feedback : BOOL;
    HeaterZone2Feedback : BOOL;
    HeaterZone3Feedback : BOOL;
    HeaterZone4Feedback : BOOL;
    DieHeaterFeedback : BOOL;
    MotorDriveHealthy : BOOL;
    FeederDriveHealthy : BOOL;
END_STRUCT
END_TYPE

TYPE ST_ExtruderAnalogInputs :
STRUCT
    Zone1Temp_C : LREAL;
    Zone2Temp_C : LREAL;
    Zone3Temp_C : LREAL;
    Zone4Temp_C : LREAL;
    DieTemp_C : LREAL;
    MeltPressure_bar : LREAL;
    MotorRpm : LREAL;
    FeederRateKgH : LREAL;
    HopperLevelPct : LREAL;
    MotorCurrent_A : LREAL;
END_STRUCT
END_TYPE

TYPE ST_ExtruderDigitalOutputs :
STRUCT
    HeaterZone1Enable : BOOL;
    HeaterZone2Enable : BOOL;
    HeaterZone3Enable : BOOL;
    HeaterZone4Enable : BOOL;
    DieHeaterEnable : BOOL;
    MotorRunEnable : BOOL;
    FeederRunEnable : BOOL;
    StackLightRed : BOOL;
    StackLightAmber : BOOL;
    StackLightGreen : BOOL;
    Horn : BOOL;
END_STRUCT
END_TYPE

TYPE ST_ExtruderAnalogOutputs :
STRUCT
    HeaterZone1Pct : LREAL;
    HeaterZone2Pct : LREAL;
    HeaterZone3Pct : LREAL;
    HeaterZone4Pct : LREAL;
    DieHeaterPct : LREAL;
    MotorSpeedRefRpm : LREAL;
    FeederRateRefKgH : LREAL;
END_STRUCT
END_TYPE

TYPE ST_ExtruderStatus :
STRUCT
    State : E_ControllerState_Tc;
    SafetyState : E_SafetyState_Tc;
    Mode : E_ExtruderMode_Tc;
    ActiveRecipeId : E_RecipeId_Tc;
    ActiveRecipeName : STRING(32);
    ReadyToStart : BOOL;
    Running : BOOL;
    Faulted : BOOL;
    RunTime_s : LREAL;
    ScanNumber : UDINT;
    AnyWarning : BOOL;
    AnyAlarm : BOOL;
    HeaterAllAtSetpoint : BOOL;
    DieAtSetpoint : BOOL;
    FeedRateSetpointKgH : LREAL;
    ScrewRpmSetpoint : LREAL;
    Zone1Setpoint_C : LREAL;
    Zone2Setpoint_C : LREAL;
    Zone3Setpoint_C : LREAL;
    Zone4Setpoint_C : LREAL;
    DieSetpoint_C : LREAL;
    AlarmSummary : ST_ExtruderAlarmSummary;
    Permissives : ST_ExtruderPermissives;
END_STRUCT
END_TYPE
