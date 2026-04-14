(*
    Example top-level program wiring the PLC function blocks together.

    This is a guide for integration, not a finished hardware project.
    Replace TempPV/RpmPV/LevelPV variables with real I/O or mapped tags.
*)

PROGRAM PRG_ExtruderCell
VAR
    Ctrl : FB_ExtruderController;
    Zone1 : FB_HeatingZone;
    Zone2 : FB_HeatingZone;
    Zone3 : FB_HeatingZone;
    Zone4 : FB_HeatingZone;
    Die : FB_DieZone;
    Feeder : FB_MaterialFeeder;
    Motor : FB_ExtrusionMotor;
    Safety : FB_SafetySystem;

    StartPB : BOOL;
    StopPB : BOOL;
    ResetPB : BOOL;
    EStopPB : BOOL;

    Z1TempPV : REAL;
    Z2TempPV : REAL;
    Z3TempPV : REAL;
    Z4TempPV : REAL;
    DieTempPV : REAL;
    MotorRpmPV : REAL;
    FeederRatePV : REAL;
    HopperLevelPctPV : REAL;
END_VAR

Zone1(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := Z1TempPV,
    Setpoint := 180.0
);
Zone2(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := Z2TempPV,
    Setpoint := 200.0
);
Zone3(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := Z3TempPV,
    Setpoint := 220.0
);
Zone4(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := Z4TempPV,
    Setpoint := 230.0
);

Feeder(
    RunCmd := Ctrl.FeederRunCmd,
    ResetCmd := Ctrl.ResetFeederFaultCmd,
    FeedRateSetpointKgH := Ctrl.FeedRateSetpoint,
    ActualRatePVKgH := FeederRatePV,
    HopperLevelPctPV := HopperLevelPctPV
);

Die(
    EnableCmd := Ctrl.DieEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := DieTempPV,
    ScrewRpmPV := MotorRpmPV,
    FeedRateActualKgH := FeederRatePV
);

Motor(
    RunCmd := Ctrl.MotorRunCmd,
    ResetCmd := Ctrl.ResetMotorFaultCmd,
    SpeedSetpointRpm := Ctrl.ScrewRpmSetpoint,
    ActualRpmPV := MotorRpmPV,
    MeltPressureBar := Die.MeltPressureBar
);

Safety(
    ResetCmd := Ctrl.ResetSafetyCmd,
    HardwareEStop := EStopPB,
    SoftwareEStop := FALSE,
    AnyZoneOverTemp :=
        Zone1.OverTempAlarm OR
        Zone2.OverTempAlarm OR
        Zone3.OverTempAlarm OR
        Zone4.OverTempAlarm,
    DieOverPressure := Die.OverPressureAlarm,
    MotorFault := Motor.FaultActive,
    WarningPresent :=
        Zone1.UnderTempAlarm OR
        Zone2.UnderTempAlarm OR
        Zone3.UnderTempAlarm OR
        Zone4.UnderTempAlarm OR
        Die.HighPressureWarning OR
        Feeder.LowMaterialAlarm OR
        Motor.StallWarning,
    WatchdogHealthy := TRUE
);

Ctrl(
    StartCmd := StartPB,
    StopCmd := StopPB,
    ResetCmd := ResetPB,
    EmergencyStopCmd := FALSE,
    SafetyEStop := Safety.EStopActive,
    HeaterAllAtSetpoint :=
        Zone1.AtSetpoint AND
        Zone2.AtSetpoint AND
        Zone3.AtSetpoint AND
        Zone4.AtSetpoint,
    DieAtSetpoint := Die.AtSetpoint,
    MotorActualRpm := MotorRpmPV,
    RecipeFeedRateCmd := 50.0,
    RecipeScrewRpmCmd := 80.0,
    CycleTime_s := 0.1
);

END_PROGRAM
