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
        )
        adapter = create_adapter(settings)
        assert isinstance(adapter, ModbusPlcAdapter)
        assert adapter.command_coil_base == 10
        assert adapter.status_base_register == 1200
        assert adapter.command_base_register == 2200
        diagnostics = adapter.diagnostics()
        assert diagnostics["connected"] is False
        assert diagnostics["last_error"]

    def test_modbus_service_can_be_created_for_commissioning(self):
        settings = AppSettings(plc_mode="modbus")
        service = create_service(settings)
        status = service.machine_status()
        assert status["plc_mode"] == "modbus"
        assert status["state"] == "UNAVAILABLE"
