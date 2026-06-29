"""Tests for the application-layer machine service."""

import csv
import io

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
    def test_default_operation_mode_is_auto(self):
        service = _make_service()
        status = service.operation_mode_status()
        assert status["mode"] == "auto"
        assert status["automatic_commands_enabled"] is True

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

    def test_production_report_csv_uses_valid_csv_escaping(self):
        service = _make_service()
        csv_text = service.production_report_csv(report_name="Trial, Shift 1")
        rows = list(csv.reader(io.StringIO(csv_text)))
        assert rows[0] == ["field", "value"]
        assert ["report_name", "Trial, Shift 1"] in rows

    def test_connection_status_returns_adapter_diagnostics(self):
        service = _make_service()
        diagnostics = service.connection_status()
        assert diagnostics["plc_mode"] == "simulation"
        assert diagnostics["connected"] is True

    def test_automation_overview_exposes_auto_mode(self):
        service = _make_service()
        overview = service.automation_overview()
        assert overview["system_type"] == "automated-extruder-system"
        assert overview["supervisory_mode"] == "auto"
        assert overview["can_apply_recipe"] is True
        assert overview["runtime_ready"] is False

    def test_manual_mode_blocks_automatic_start(self):
        service = _make_service()
        service.set_operation_mode("manual")

        try:
            service.start_machine()
        except Exception as exc:
            assert "auto mode" in str(exc)
        else:
            raise AssertionError("Expected manual mode to block automatic start")

    def test_maintenance_mode_blocks_recipe_changes(self):
        service = _make_service()
        service.set_operation_mode("maintenance")

        try:
            service.apply_recipe(ActiveRecipeUpdate(recipe_id="general-purpose"))
        except Exception as exc:
            assert "maintenance mode" in str(exc)
        else:
            raise AssertionError("Expected maintenance mode to block recipe changes")

    def test_cannot_change_mode_while_running_sequence(self):
        service = _make_service()
        service.start_machine()

        try:
            service.set_operation_mode("manual")
        except Exception as exc:
            assert "idle or in emergency stop" in str(exc)
        else:
            raise AssertionError("Expected mode change to be rejected while startup is active")

    def test_browse_connection_nodes_uses_adapter_support(self):
        service = _make_service()
        assert service.browse_connection_nodes() == []
