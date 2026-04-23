"""Tests for application factory and settings helpers."""

from extruder_app.factory import create_adapter, create_service
from extruder_app.plc_adapters import ModbusPlcAdapter, SimulationPlcAdapter
from extruder_app.settings import AppSettings


class TestApplicationFactory:
    def test_simulation_mode_returns_simulation_adapter(self):
        settings = AppSettings(plc_mode="simulation")
        adapter = create_adapter(settings)
        assert isinstance(adapter, SimulationPlcAdapter)

    def test_invalid_mode_raises(self):
        settings = AppSettings(plc_mode="invalid-mode")
        try:
            create_adapter(settings)
        except ValueError as exc:
            assert "Unsupported EXTRUDER_PLC_MODE" in str(exc)
        else:
            raise AssertionError("Expected invalid PLC mode to raise ValueError")

    def test_simulation_adapter_reports_diagnostics(self):
        settings = AppSettings(plc_mode="simulation")
        adapter = create_adapter(settings)
        diagnostics = adapter.diagnostics()
        assert diagnostics["plc_mode"] == "simulation"
        assert diagnostics["connected"] is True

    def test_modbus_mode_returns_placeholder_adapter(self):
        settings = AppSettings(
            plc_mode="modbus",
            modbus_command_coil_base=10,
            modbus_status_base_register=1200,
            modbus_command_base_register=2200,
            modbus_command_coil_map={"start": 5, "stop": 6, "reset": 7, "emergency_stop": 8, "acknowledge_alarms": 9},
            modbus_status_register_map={"state": 0, "scan_number_hi": 1, "scan_number_lo": 2, "run_time_hi": 3, "run_time_lo": 4, "safety_state": 5, "alarm_summary": 6, "flags": 7, "feed_rate_setpoint": 8, "screw_rpm_setpoint": 9, "zone1_sp": 10, "zone2_sp": 11, "zone3_sp": 12, "zone4_sp": 13, "die_sp": 14, "zone1_temp": 15, "zone2_temp": 16, "zone3_temp": 17, "zone4_temp": 18, "die_temp": 19, "pressure_bar": 20, "motor_rpm": 30, "motor_current": 22, "feeder_rate": 23, "hopper_level": 24},
            modbus_command_register_map={"feed_rate_setpoint": 0, "screw_rpm_setpoint": 1, "zone1_sp": 2, "zone2_sp": 3, "zone3_sp": 4, "zone4_sp": 5, "die_sp": 10},
        )
        adapter = create_adapter(settings)
        assert isinstance(adapter, ModbusPlcAdapter)
        assert adapter.command_coil_base == 10
        assert adapter.status_base_register == 1200
        assert adapter.command_base_register == 2200
        assert adapter.command_coil_map["start"] == 5
        assert adapter.status_register_map["motor_rpm"] == 30
        assert adapter.command_register_map["die_sp"] == 10
        diagnostics = adapter.diagnostics()
        assert diagnostics["connected"] is False
        assert diagnostics["last_error"]

    def test_modbus_service_can_be_created_for_commissioning(self):
        settings = AppSettings(plc_mode="modbus")
        service = create_service(settings)
        status = service.machine_status()
        assert status["plc_mode"] == "modbus"
        assert status["state"] == "UNAVAILABLE"

    def test_settings_from_env_parses_modbus_maps(self, monkeypatch):
        monkeypatch.setenv("EXTRUDER_MODBUS_COMMAND_COIL_MAP_JSON", '{"start":12}')
        monkeypatch.setenv("EXTRUDER_MODBUS_STATUS_REGISTER_MAP_JSON", '{"motor_rpm":30}')
        monkeypatch.setenv("EXTRUDER_MODBUS_COMMAND_REGISTER_MAP_JSON", '{"die_sp":10}')

        settings = AppSettings.from_env()

        assert settings.modbus_command_coil_map["start"] == 12
        assert settings.modbus_status_register_map["motor_rpm"] == 30
        assert settings.modbus_command_register_map["die_sp"] == 10
