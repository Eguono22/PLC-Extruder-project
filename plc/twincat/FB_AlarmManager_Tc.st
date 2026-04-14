FUNCTION_BLOCK FB_AlarmManager_Tc
VAR_INPUT
    Warning01 : BOOL;
    Warning02 : BOOL;
    Warning03 : BOOL;
    Warning04 : BOOL;
    Warning05 : BOOL;
    Fault01 : BOOL;
    Fault02 : BOOL;
    Fault03 : BOOL;
    Fault04 : BOOL;
    Critical01 : BOOL;
    Critical02 : BOOL;
    Critical03 : BOOL;
END_VAR
VAR_OUTPUT
    Summary : ST_ExtruderAlarmSummary;
END_VAR
VAR
    AlarmWord : DWORD;
END_VAR

Summary.WarningCount := 0;
Summary.FaultCount := 0;
Summary.CriticalCount := 0;
AlarmWord := DWORD#0;

IF Warning01 THEN Summary.WarningCount := Summary.WarningCount + 1; AlarmWord := AlarmWord OR DWORD#16#0001; END_IF;
IF Warning02 THEN Summary.WarningCount := Summary.WarningCount + 1; AlarmWord := AlarmWord OR DWORD#16#0002; END_IF;
IF Warning03 THEN Summary.WarningCount := Summary.WarningCount + 1; AlarmWord := AlarmWord OR DWORD#16#0004; END_IF;
IF Warning04 THEN Summary.WarningCount := Summary.WarningCount + 1; AlarmWord := AlarmWord OR DWORD#16#0008; END_IF;
IF Warning05 THEN Summary.WarningCount := Summary.WarningCount + 1; AlarmWord := AlarmWord OR DWORD#16#0010; END_IF;

IF Fault01 THEN Summary.FaultCount := Summary.FaultCount + 1; AlarmWord := AlarmWord OR DWORD#16#0100; END_IF;
IF Fault02 THEN Summary.FaultCount := Summary.FaultCount + 1; AlarmWord := AlarmWord OR DWORD#16#0200; END_IF;
IF Fault03 THEN Summary.FaultCount := Summary.FaultCount + 1; AlarmWord := AlarmWord OR DWORD#16#0400; END_IF;
IF Fault04 THEN Summary.FaultCount := Summary.FaultCount + 1; AlarmWord := AlarmWord OR DWORD#16#0800; END_IF;

IF Critical01 THEN Summary.CriticalCount := Summary.CriticalCount + 1; AlarmWord := AlarmWord OR DWORD#16#10000; END_IF;
IF Critical02 THEN Summary.CriticalCount := Summary.CriticalCount + 1; AlarmWord := AlarmWord OR DWORD#16#20000; END_IF;
IF Critical03 THEN Summary.CriticalCount := Summary.CriticalCount + 1; AlarmWord := AlarmWord OR DWORD#16#40000; END_IF;

Summary.AnyWarning := Summary.WarningCount > 0;
Summary.AnyFault := Summary.FaultCount > 0;
Summary.AnyCritical := Summary.CriticalCount > 0;
Summary.AlarmWord := AlarmWord;

END_FUNCTION_BLOCK
