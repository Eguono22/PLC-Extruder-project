VAR_GLOBAL
    gExtruderCmd : ST_ExtruderCommands := (
        Mode := E_ExtruderMode_Tc.AUTO,
        RecipeId := E_RecipeId_Tc.DEFAULT,
        RecipeFeedRateKgH := 50.0,
        RecipeScrewRpm := 80.0,
        Zone1Setpoint_C := 180.0,
        Zone2Setpoint_C := 200.0,
        Zone3Setpoint_C := 220.0,
        Zone4Setpoint_C := 230.0,
        DieSetpoint_C := 235.0
    );

    gExtruderDI : ST_ExtruderDigitalInputs;
    gExtruderAI : ST_ExtruderAnalogInputs;

    gExtruderDO : ST_ExtruderDigitalOutputs;
    gExtruderAO : ST_ExtruderAnalogOutputs;

    gExtruderStatus : ST_ExtruderStatus := (
        State := E_ControllerState_Tc.IDLE,
        SafetyState := E_SafetyState_Tc.SAFE,
        Mode := E_ExtruderMode_Tc.AUTO,
        ActiveRecipeId := E_RecipeId_Tc.DEFAULT
    );
END_VAR
