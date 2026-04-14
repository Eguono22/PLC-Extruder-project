{attribute 'qualified_only'}
VAR_GLOBAL CONSTANT
    cCycleTime_s : LREAL := 0.1;

    cBarrelZone1Setpoint_C : LREAL := 180.0;
    cBarrelZone2Setpoint_C : LREAL := 200.0;
    cBarrelZone3Setpoint_C : LREAL := 220.0;
    cBarrelZone4Setpoint_C : LREAL := 230.0;
    cDieSetpoint_C : LREAL := 235.0;
    cTempTolerance_C : LREAL := 5.0;

    cMotorMinRpm : LREAL := 5.0;
    cMotorMaxRpm : LREAL := 150.0;
    cFeedMinKgH : LREAL := 5.0;
    cFeedMaxKgH : LREAL := 100.0;

    cDiePressureWarning_bar : LREAL := 300.0;
    cDiePressureMax_bar : LREAL := 350.0;
    cMaxBarrelTemp_C : LREAL := 280.0;

    cLowMaterialLevel_pct : LREAL := 10.0;
    cEmptyMaterialLevel_pct : LREAL := 2.0;
END_VAR
