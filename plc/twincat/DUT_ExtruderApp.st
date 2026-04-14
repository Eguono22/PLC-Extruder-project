{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_ExtruderMode_Tc :
(
    OFF := 0,
    MANUAL := 10,
    AUTO := 20,
    MAINTENANCE := 30
);
END_TYPE

{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_RecipeId_Tc :
(
    DEFAULT := 0,
    HDPE_PIPE := 10,
    PVC_PROFILE := 20,
    CUSTOM := 100
);
END_TYPE

TYPE ST_ExtruderRecipe :
STRUCT
    Name : STRING(32);
    Zone1Setpoint_C : LREAL;
    Zone2Setpoint_C : LREAL;
    Zone3Setpoint_C : LREAL;
    Zone4Setpoint_C : LREAL;
    DieSetpoint_C : LREAL;
    FeedRateKgH : LREAL;
    ScrewRpm : LREAL;
END_STRUCT
END_TYPE

TYPE ST_ExtruderPermissives :
STRUCT
    EStopHealthy : BOOL;
    GuardDoorClosed : BOOL;
    MotorDriveHealthy : BOOL;
    FeederDriveHealthy : BOOL;
    HopperMaterialAvailable : BOOL;
    ReadyToStart : BOOL;
END_STRUCT
END_TYPE

TYPE ST_ExtruderAlarmSummary :
STRUCT
    WarningCount : UINT;
    FaultCount : UINT;
    CriticalCount : UINT;
    AnyWarning : BOOL;
    AnyFault : BOOL;
    AnyCritical : BOOL;
    AlarmWord : DWORD;
END_STRUCT
END_TYPE
