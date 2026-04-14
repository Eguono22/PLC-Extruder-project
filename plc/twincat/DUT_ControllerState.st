{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_ControllerState_Tc :
(
    IDLE := 0,
    STARTUP := 10,
    RUNNING := 20,
    SHUTDOWN := 30,
    EMERGENCY_STOP := 40
);
END_TYPE
