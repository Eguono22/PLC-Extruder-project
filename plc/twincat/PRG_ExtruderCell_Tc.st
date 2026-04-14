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
    RecipeMgr : FB_RecipeManager_Tc;
    AlarmMgr : FB_AlarmManager_Tc;
    Zone1 : FB_HeatingZone;
    Zone2 : FB_HeatingZone;
    Zone3 : FB_HeatingZone;
    Zone4 : FB_HeatingZone;
    Die : FB_DieZone;
    Feeder : FB_MaterialFeeder;
    Motor : FB_ExtrusionMotor;
    ActiveRecipe : ST_ExtruderRecipe;
    CustomRecipe : ST_ExtruderRecipe;
    SafetyState : E_SafetyState_Tc := E_SafetyState_Tc.SAFE;
    SafetyEStopActive : BOOL;
    AnyWarning : BOOL;
    AnyFault : BOOL;
    AutoStartPermissive : BOOL;
    Permissives : ST_ExtruderPermissives;
END_VAR

CustomRecipe.Name := 'Custom';
CustomRecipe.Zone1Setpoint_C := gExtruderCmd.Zone1Setpoint_C;
CustomRecipe.Zone2Setpoint_C := gExtruderCmd.Zone2Setpoint_C;
CustomRecipe.Zone3Setpoint_C := gExtruderCmd.Zone3Setpoint_C;
CustomRecipe.Zone4Setpoint_C := gExtruderCmd.Zone4Setpoint_C;
CustomRecipe.DieSetpoint_C := gExtruderCmd.DieSetpoint_C;
CustomRecipe.FeedRateKgH := gExtruderCmd.RecipeFeedRateKgH;
CustomRecipe.ScrewRpm := gExtruderCmd.RecipeScrewRpm;

RecipeMgr(
    SelectedRecipeId := gExtruderCmd.RecipeId,
    CustomRecipe := CustomRecipe
);
ActiveRecipe := RecipeMgr.ActiveRecipe;

Permissives.EStopHealthy := gExtruderDI.EStopOk;
Permissives.GuardDoorClosed := gExtruderDI.GuardDoorClosed;
Permissives.MotorDriveHealthy := gExtruderDI.MotorDriveHealthy;
Permissives.FeederDriveHealthy := gExtruderDI.FeederDriveHealthy;
Permissives.HopperMaterialAvailable := gExtruderAI.HopperLevelPct > GVL_ExtruderConfig.cEmptyMaterialLevel_pct;
Permissives.ReadyToStart :=
    Permissives.EStopHealthy AND
    Permissives.GuardDoorClosed AND
    Permissives.MotorDriveHealthy AND
    Permissives.FeederDriveHealthy AND
    Permissives.HopperMaterialAvailable;

AutoStartPermissive :=
    (gExtruderCmd.Mode = E_ExtruderMode_Tc.AUTO) AND
    Permissives.ReadyToStart;

Zone1(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := REAL(gExtruderAI.Zone1Temp_C),
    Setpoint := REAL(ActiveRecipe.Zone1Setpoint_C),
    TempTolerance := REAL(GVL_ExtruderConfig.cTempTolerance_C),
    MaxTemp := REAL(GVL_ExtruderConfig.cMaxBarrelTemp_C)
);
Zone2(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := REAL(gExtruderAI.Zone2Temp_C),
    Setpoint := REAL(ActiveRecipe.Zone2Setpoint_C),
    TempTolerance := REAL(GVL_ExtruderConfig.cTempTolerance_C),
    MaxTemp := REAL(GVL_ExtruderConfig.cMaxBarrelTemp_C)
);
Zone3(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := REAL(gExtruderAI.Zone3Temp_C),
    Setpoint := REAL(ActiveRecipe.Zone3Setpoint_C),
    TempTolerance := REAL(GVL_ExtruderConfig.cTempTolerance_C),
    MaxTemp := REAL(GVL_ExtruderConfig.cMaxBarrelTemp_C)
);
Zone4(
    EnableCmd := Ctrl.HeaterEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := REAL(gExtruderAI.Zone4Temp_C),
    Setpoint := REAL(ActiveRecipe.Zone4Setpoint_C),
    TempTolerance := REAL(GVL_ExtruderConfig.cTempTolerance_C),
    MaxTemp := REAL(GVL_ExtruderConfig.cMaxBarrelTemp_C)
);

Feeder(
    RunCmd := Ctrl.FeederRunCmd,
    ResetCmd := Ctrl.ResetFeederFaultCmd,
    FeedRateSetpointKgH := REAL(Ctrl.FeedRateSetpoint),
    ActualRatePVKgH := REAL(gExtruderAI.FeederRateKgH),
    HopperLevelPctPV := REAL(gExtruderAI.HopperLevelPct),
    MinRateKgH := REAL(GVL_ExtruderConfig.cFeedMinKgH),
    MaxRateKgH := REAL(GVL_ExtruderConfig.cFeedMaxKgH),
    LowLevelPct := REAL(GVL_ExtruderConfig.cLowMaterialLevel_pct),
    EmptyLevelPct := REAL(GVL_ExtruderConfig.cEmptyMaterialLevel_pct)
);

Die(
    EnableCmd := Ctrl.DieEnableCmd,
    ResetCmd := Ctrl.ResetSafetyCmd,
    TemperaturePV := REAL(gExtruderAI.DieTemp_C),
    Setpoint := REAL(ActiveRecipe.DieSetpoint_C),
    TempTolerance := REAL(GVL_ExtruderConfig.cTempTolerance_C),
    MaxTemp := REAL(GVL_ExtruderConfig.cMaxBarrelTemp_C),
    ScrewRpmPV := REAL(gExtruderAI.MotorRpm),
    FeedRateActualKgH := REAL(gExtruderAI.FeederRateKgH),
    MotorMaxRpm := REAL(GVL_ExtruderConfig.cMotorMaxRpm),
    DieMaxPressureBar := REAL(GVL_ExtruderConfig.cDiePressureMax_bar),
    DieWarningPressureBar := REAL(GVL_ExtruderConfig.cDiePressureWarning_bar)
);

Motor(
    RunCmd := Ctrl.MotorRunCmd,
    ResetCmd := Ctrl.ResetMotorFaultCmd,
    SpeedSetpointRpm := REAL(Ctrl.ScrewRpmSetpoint),
    ActualRpmPV := REAL(gExtruderAI.MotorRpm),
    MeltPressureBar := REAL(gExtruderAI.MeltPressure_bar),
    MinRpm := REAL(GVL_ExtruderConfig.cMotorMinRpm),
    MaxRpm := REAL(GVL_ExtruderConfig.cMotorMaxRpm),
    DieMaxPressureBar := REAL(GVL_ExtruderConfig.cDiePressureMax_bar)
);

AnyWarning :=
    Zone1.UnderTempAlarm OR
    Zone2.UnderTempAlarm OR
    Zone3.UnderTempAlarm OR
    Zone4.UnderTempAlarm OR
    Die.HighPressureWarning OR
    Feeder.LowMaterialAlarm OR
    Motor.StallWarning;

AnyFault :=
    Feeder.FaultActive OR
    Motor.FaultActive;

SafetyEStopActive :=
    (NOT Permissives.EStopHealthy) OR
    (NOT Permissives.GuardDoorClosed) OR
    (NOT Permissives.MotorDriveHealthy) OR
    (NOT Permissives.FeederDriveHealthy) OR
    gExtruderCmd.EmergencyStop OR
    Zone1.OverTempAlarm OR
    Zone2.OverTempAlarm OR
    Zone3.OverTempAlarm OR
    Zone4.OverTempAlarm OR
    Die.OverPressureAlarm OR
    Motor.FaultActive;

AlarmMgr(
    Warning01 := Zone1.UnderTempAlarm,
    Warning02 := Zone2.UnderTempAlarm,
    Warning03 := Zone3.UnderTempAlarm,
    Warning04 := Zone4.UnderTempAlarm,
    Warning05 := Die.HighPressureWarning OR Feeder.LowMaterialAlarm OR Motor.StallWarning,
    Fault01 := Feeder.FaultActive,
    Fault02 := Motor.FaultActive,
    Fault03 := NOT Permissives.MotorDriveHealthy,
    Fault04 := NOT Permissives.FeederDriveHealthy,
    Critical01 := NOT Permissives.EStopHealthy OR gExtruderCmd.EmergencyStop,
    Critical02 := NOT Permissives.GuardDoorClosed,
    Critical03 := Zone1.OverTempAlarm OR Zone2.OverTempAlarm OR Zone3.OverTempAlarm OR Zone4.OverTempAlarm OR Die.OverPressureAlarm
);

IF SafetyEStopActive THEN
    SafetyState := E_SafetyState_Tc.E_STOP;
ELSIF AnyWarning THEN
    SafetyState := E_SafetyState_Tc.WARNING;
ELSE
    SafetyState := E_SafetyState_Tc.SAFE;
END_IF;

Ctrl(
    StartCmd := gExtruderCmd.Start AND AutoStartPermissive,
    StopCmd := gExtruderCmd.Stop OR (gExtruderCmd.Mode = E_ExtruderMode_Tc.OFF),
    ResetCmd := gExtruderCmd.Reset,
    EmergencyStopCmd := gExtruderCmd.EmergencyStop,
    SafetyEStop := SafetyEStopActive,
    HeaterAllAtSetpoint :=
        Zone1.AtSetpoint AND
        Zone2.AtSetpoint AND
        Zone3.AtSetpoint AND
        Zone4.AtSetpoint,
    DieAtSetpoint := Die.AtSetpoint,
    MotorActualRpm := gExtruderAI.MotorRpm,
    RecipeFeedRateCmd := ActiveRecipe.FeedRateKgH,
    RecipeScrewRpmCmd := ActiveRecipe.ScrewRpm,
    CycleTime_s := GVL_ExtruderConfig.cCycleTime_s
);

gExtruderDO.HeaterZone1Enable := Zone1.HeaterEnable;
gExtruderDO.HeaterZone2Enable := Zone2.HeaterEnable;
gExtruderDO.HeaterZone3Enable := Zone3.HeaterEnable;
gExtruderDO.HeaterZone4Enable := Zone4.HeaterEnable;
gExtruderDO.DieHeaterEnable := Die.HeaterEnable;
gExtruderDO.MotorRunEnable := Motor.MotorEnable;
gExtruderDO.FeederRunEnable := Feeder.FeederEnable;
gExtruderDO.StackLightRed := SafetyEStopActive;
gExtruderDO.StackLightAmber := AnyWarning AND NOT SafetyEStopActive;
gExtruderDO.StackLightGreen := Ctrl.State = E_ControllerState_Tc.RUNNING;
gExtruderDO.Horn := SafetyEStopActive;

gExtruderAO.HeaterZone1Pct := Zone1.HeaterOutputPct;
gExtruderAO.HeaterZone2Pct := Zone2.HeaterOutputPct;
gExtruderAO.HeaterZone3Pct := Zone3.HeaterOutputPct;
gExtruderAO.HeaterZone4Pct := Zone4.HeaterOutputPct;
gExtruderAO.DieHeaterPct := Die.HeaterOutputPct;
gExtruderAO.MotorSpeedRefRpm := Ctrl.ScrewRpmSetpoint;
gExtruderAO.FeederRateRefKgH := Ctrl.FeedRateSetpoint;

gExtruderStatus.State := Ctrl.State;
gExtruderStatus.SafetyState := SafetyState;
gExtruderStatus.Mode := gExtruderCmd.Mode;
gExtruderStatus.ActiveRecipeId := RecipeMgr.ActiveRecipeId;
gExtruderStatus.ActiveRecipeName := ActiveRecipe.Name;
gExtruderStatus.ReadyToStart := Permissives.ReadyToStart AND NOT SafetyEStopActive;
gExtruderStatus.Running := Ctrl.State = E_ControllerState_Tc.RUNNING;
gExtruderStatus.Faulted := SafetyEStopActive OR AnyFault;
gExtruderStatus.RunTime_s := Ctrl.RunTime_s;
gExtruderStatus.ScanNumber := Ctrl.ScanNumber;
gExtruderStatus.AnyWarning := AnyWarning;
gExtruderStatus.AnyAlarm := AlarmMgr.Summary.AnyWarning OR AlarmMgr.Summary.AnyFault OR AlarmMgr.Summary.AnyCritical;
gExtruderStatus.HeaterAllAtSetpoint :=
    Zone1.AtSetpoint AND
    Zone2.AtSetpoint AND
    Zone3.AtSetpoint AND
    Zone4.AtSetpoint;
gExtruderStatus.DieAtSetpoint := Die.AtSetpoint;
gExtruderStatus.FeedRateSetpointKgH := Ctrl.FeedRateSetpoint;
gExtruderStatus.ScrewRpmSetpoint := Ctrl.ScrewRpmSetpoint;
gExtruderStatus.Zone1Setpoint_C := ActiveRecipe.Zone1Setpoint_C;
gExtruderStatus.Zone2Setpoint_C := ActiveRecipe.Zone2Setpoint_C;
gExtruderStatus.Zone3Setpoint_C := ActiveRecipe.Zone3Setpoint_C;
gExtruderStatus.Zone4Setpoint_C := ActiveRecipe.Zone4Setpoint_C;
gExtruderStatus.DieSetpoint_C := ActiveRecipe.DieSetpoint_C;
gExtruderStatus.AlarmSummary := AlarmMgr.Summary;
gExtruderStatus.Permissives := Permissives;

END_PROGRAM
