"""Tests for automation/HMI summaries."""

from extruder_app.automation import build_automation_overview


def test_build_automation_overview_marks_warm_line_ready_for_start():
    overview = build_automation_overview(
        system_name="Extruder HMI",
        machine={
            "state": "IDLE",
            "safety": {"state": "SAFE"},
            "heater": {"all_at_setpoint": True},
            "die": {"temperature_c": 225.0, "setpoint_c": 225.0},
            "active_alarms": [],
            "active_recipe": {"name": "General Purpose"},
        },
        runtime={"ready": True},
        connection={"connected": True},
        operation_mode={
            "mode": "auto",
            "automatic_commands_enabled": True,
            "recipe_edits_enabled": True,
        },
    )

    assert overview["ready_for_start"] is True
    assert overview["next_operator_action"] == "Start the automatic line sequence"
    assert any("thermally ready" in note for note in overview["notes"])
