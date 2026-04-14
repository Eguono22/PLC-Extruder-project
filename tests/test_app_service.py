"""Tests for the application-layer machine service."""

from extruder_app.logging_store import TelemetryStore
from extruder_app.models import ActiveRecipeUpdate, ZoneSetpoints
from extruder_app.plc_adapters import SimulationPlcAdapter
from extruder_app.service import ExtruderApplicationService


def _make_service() -> ExtruderApplicationService:
    return ExtruderApplicationService(
        adapter=SimulationPlcAdapter(),
        telemetry=TelemetryStore(persist_to_disk=False),
        scan_interval_s=0.0,
    )


class TestExtruderApplicationService:
    def test_default_recipe_loaded(self):
        service = _make_service()
        recipe = service.active_recipe()
        assert recipe.recipe_id == "general-purpose"

    def test_apply_custom_recipe_updates_active_recipe(self):
        service = _make_service()
        updated = service.apply_recipe(
            ActiveRecipeUpdate(
                recipe_id="custom",
                name="Custom Trial",
                feed_rate_kg_h=55.0,
                screw_rpm=70.0,
                zone_setpoints=ZoneSetpoints(
                    barrel_c=[170.0, 180.0, 190.0, 200.0],
                    die_c=205.0,
                ),
            )
        )
        assert updated.name == "Custom Trial"
        assert service.active_recipe().feed_rate_kg_h == 55.0

    def test_poll_once_records_telemetry(self):
        service = _make_service()
        snapshot = service.poll_once()
        assert snapshot["state"] == "IDLE"
        analytics = service.analytics_summary()
        assert analytics["total_samples"] >= 1

    def test_start_command_is_processed(self):
        service = _make_service()
        accepted = service.start_machine()
        assert accepted is True

    def test_recent_events_include_control_commands(self):
        service = _make_service()
        service.start_machine()
        events = service.recent_events(limit=10)
        assert any(event["type"] == "start_command" for event in events)

    def test_production_report_returns_expected_shape(self):
        service = _make_service()
        service.poll_once()
        report = service.production_report()
        assert report["report_name"] == "Production Report"
        assert "avg_throughput_kg_h" in report
        assert "event_count" in report

    def test_connection_status_returns_adapter_diagnostics(self):
        service = _make_service()
        diagnostics = service.connection_status()
        assert diagnostics["plc_mode"] == "simulation"
        assert diagnostics["connected"] is True

    def test_browse_connection_nodes_uses_adapter_support(self):
        service = _make_service()
        assert service.browse_connection_nodes() == []
