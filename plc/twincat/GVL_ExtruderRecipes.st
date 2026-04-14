VAR_GLOBAL CONSTANT
    gcRecipeDefault : ST_ExtruderRecipe := (
        Name := 'Default Extrusion',
        Zone1Setpoint_C := 180.0,
        Zone2Setpoint_C := 200.0,
        Zone3Setpoint_C := 220.0,
        Zone4Setpoint_C := 230.0,
        DieSetpoint_C := 235.0,
        FeedRateKgH := 50.0,
        ScrewRpm := 80.0
    );

    gcRecipeHdpePipe : ST_ExtruderRecipe := (
        Name := 'HDPE Pipe',
        Zone1Setpoint_C := 175.0,
        Zone2Setpoint_C := 195.0,
        Zone3Setpoint_C := 210.0,
        Zone4Setpoint_C := 220.0,
        DieSetpoint_C := 225.0,
        FeedRateKgH := 62.0,
        ScrewRpm := 92.0
    );

    gcRecipePvcProfile : ST_ExtruderRecipe := (
        Name := 'PVC Profile',
        Zone1Setpoint_C := 165.0,
        Zone2Setpoint_C := 178.0,
        Zone3Setpoint_C := 186.0,
        Zone4Setpoint_C := 192.0,
        DieSetpoint_C := 195.0,
        FeedRateKgH := 42.0,
        ScrewRpm := 58.0
    );
END_VAR
