(*
    Beckhoff TwinCAT integration example for the extruder cell.

    Notes:
    - Map *_PV variables to EtherCAT or terminal I/O.
    - For production work, replace the generic component blocks with
      TwinCAT library-backed FBs where appropriate.
*)

PROGRAM PRG_ExtruderCell_Tc
VAR
    Ctrl : FB_ExtruderController_Tc;
    Zone1 : FB_HeatingZone;
    Zone2 : FB_HeatingZone;
    Zone3 : FB_HeatingZone;
    Zone4 : FB_HeatingZone;
    Die : FB_DieZone;
    Feeder : FB_MaterialFeeder;
    Motor : FB_ExtrusionMotor;
    SafetyEStopActive : BOOL;

    StartPB : BOOL;
    StopPB : BOOL;
    ResetPB : BOOL;
    EStopPB : BOOL;

    Z1TempPV_C : REAL;
    Z2TempPV_C : REAL;
    Z3TempPV_C : REAL;
    Z4TempPV_C : REAL;
    DieTempPV_C : REAL;
    MotorRpmPV : REAL;
    FeederRatePV_KgH : REAL;
    HopperLevelPctPV : REAL;
END_VAR

Zone1(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := Z1TempPV_C,
    Setpoint := GVL_ExtruderConfig.cBarrelZone1Setpoint_C,
    TempTolerance := GVL_ExtruderConfig.cTempTolerance_C,
    MaxTemp := GVL_ExtruderConfig.cMaxBarrelTemp_C
);
Zone2(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := Z2TempPV_C,
    Setpoint := GVL_ExtruderConfig.cBarrelZone2Setpoint_C,
    TempTolerance := GVL_ExtruderConfig.cTempTolerance_C,
    MaxTemp := GVL_ExtruderConfig.cMaxBarrelTemp_C
);
Zone3(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := Z3TempPV_C,
    Setpoint := GVL_ExtruderConfig.cBarrelZone3Setpoint_C,
    TempTolerance := GVL_ExtruderConfig.cTempTolerance_C,
    MaxTemp := GVL_ExtruderConfig.cMaxBarrelTemp_C
);
Zone4(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := Z4TempPV_C,
    Setpoint := GVL_ExtruderConfig.cBarrelZone4Setpoint_C,
    TempTolerance := GVL_ExtruderConfig.cTempTolerance_C,
    MaxTemp := GVL_ExtruderConfig.cMaxBarrelTemp_C
);

Feeder(
    RunCmd := Ctrl.FeederRunCmd,
    ResetCmd := Ctrl.ResetFeederFaultCmd,
    FeedRateSetpointKgH := Ctrl.FeedRateSetpoint,
    ActualRatePVKgH := FeederRatePV_KgH,
    HopperLevelPctPV := HopperLevelPctPV,
    MinRateKgH := GVL_ExtruderConfig.cFeedMinKgH,
    MaxRateKgH := GVL_ExtruderConfig.cFeedMaxKgH,
    LowLevelPct := GVL_ExtruderConfig.cLowMaterialLevel_pct,
    EmptyLevelPct := GVL_ExtruderConfig.cEmptyMaterialLevel_pct
);

Die(
    EnableCmd := Ctrl.DieEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := DieTempPV_C,
    Setpoint := GVL_ExtruderConfig.cDieSetpoint_C,
    TempTolerance := GVL_ExtruderConfig.cTempTolerance_C,
    MaxTemp := GVL_ExtruderConfig.cMaxBarrelTemp_C,
    ScrewRpmPV := MotorRpmPV,
    FeedRateActualKgH := FeederRatePV_KgH,
    MotorMaxRpm := GVL_ExtruderConfig.cMotorMaxRpm,
    DieMaxPressureBar := GVL_ExtruderConfig.cDiePressureMax_bar,
    DieWarningPressureBar := GVL_ExtruderConfig.cDiePressureWarning_bar
);

Motor(
    RunCmd := Ctrl.MotorRunCmd,
    ResetCmd := Ctrl.ResetMotorFaultCmd,
    SpeedSetpointRpm := Ctrl.ScrewRpmSetpoint,
    ActualRpmPV := MotorRpmPV,
    MeltPressureBar := Die.MeltPressureBar,
    MinRpm := GVL_ExtruderConfig.cMotorMinRpm,
    MaxRpm := GVL_ExtruderConfig.cMotorMaxRpm,
    DieMaxPressureBar := GVL_ExtruderConfig.cDiePressureMax_bar
);

SafetyEStopActive :=
    EStopPB OR
    Zone1.OverTempAlarm OR
    Zone2.OverTempAlarm OR
    Zone3.OverTempAlarm OR
    Zone4.OverTempAlarm OR
    Die.OverPressureAlarm OR
    Motor.FaultActive;

Ctrl(
    StartCmd := StartPB,
    StopCmd := StopPB,
    ResetCmd := ResetPB,
    EmergencyStopCmd := FALSE,
    SafetyEStop := SafetyEStopActive,
    HeaterAllAtSetpoint :=
        Zone1.AtSetpoint AND
        Zone2.AtSetpoint AND
        Zone3.AtSetpoint AND
        Zone4.AtSetpoint,
    DieAtSetpoint := Die.AtSetpoint,
    MotorActualRpm := MotorRpmPV,
    RecipeFeedRateCmd := 50.0,
    RecipeScrewRpmCmd := 80.0,
    CycleTime_s := GVL_ExtruderConfig.cCycleTime_s
);

END_PROGRAM
