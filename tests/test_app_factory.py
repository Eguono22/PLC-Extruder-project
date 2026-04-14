"""Tests for application factory and settings helpers."""

from extruder_app.factory import create_adapter
from extruder_app.plc_adapters import SimulationPlcAdapter
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
