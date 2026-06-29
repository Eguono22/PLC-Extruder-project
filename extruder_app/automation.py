"""Automation-oriented summaries for the extruder web HMI."""

from __future__ import annotations

from typing import Dict, List


_BLOCKING_SAFETY_STATES = {"E_STOP", "FAULT", "UNKNOWN"}
_AUTOMATION_PHASES = {
    "IDLE": "standby",
    "STARTUP": "automatic-startup",
    "RUNNING": "automatic-production",
    "SHUTDOWN": "controlled-shutdown",
    "EMERGENCY_STOP": "emergency-stop",
    "UNAVAILABLE": "communications-unavailable",
}


def _die_ready(machine: Dict[str, object]) -> bool:
    die = machine.get("die", {})
    if not isinstance(die, dict):
        return False
    at_setpoint = die.get("at_setpoint")
    if at_setpoint is not None:
        return bool(at_setpoint)

    try:
        temperature_c = float(die.get("temperature_c", 0.0))
        setpoint_c = float(die.get("setpoint_c", 0.0))
    except (TypeError, ValueError):
        return False
    return abs(temperature_c - setpoint_c) <= 5.0


def build_automation_overview(
    system_name: str,
    machine: Dict[str, object],
    runtime: Dict[str, object],
    connection: Dict[str, object],
    operation_mode: Dict[str, object],
) -> Dict[str, object]:
    """Derive operator-facing automation status from machine, runtime, and PLC state."""
    state = str(machine.get("state", "UNKNOWN"))
    supervisory_mode = str(operation_mode.get("mode", "auto"))
    safety = machine.get("safety", {})
    safety_state = str(safety.get("state", "UNKNOWN")) if isinstance(safety, dict) else "UNKNOWN"
    connected = bool(connection.get("connected"))
    runtime_ready = bool(runtime.get("ready"))
    heaters_ready = bool(machine.get("heater", {}).get("all_at_setpoint")) if isinstance(
        machine.get("heater"), dict
    ) else False
    die_ready = _die_ready(machine)
    permissives_ok = safety_state not in _BLOCKING_SAFETY_STATES
    auto_sequence_active = state in {"STARTUP", "RUNNING", "SHUTDOWN"}
    mode_allows_start = bool(operation_mode.get("automatic_commands_enabled"))
    mode_allows_recipe_changes = bool(operation_mode.get("recipe_edits_enabled"))
    ready_for_start = mode_allows_start and (
        state == "IDLE" and connected and runtime_ready and permissives_ok and heaters_ready and die_ready
    )
    can_start = mode_allows_start and state == "IDLE" and connected and runtime_ready and permissives_ok
    can_stop = state in {"STARTUP", "RUNNING"}
    can_reset = state in {"IDLE", "EMERGENCY_STOP"}
    can_apply_recipe = mode_allows_recipe_changes and state in {"IDLE", "STARTUP", "RUNNING"}
    active_alarm_count = len(machine.get("active_alarms", []))
    active_recipe = machine.get("active_recipe", {})
    active_recipe_name = (
        str(active_recipe.get("name", "Unknown"))
        if isinstance(active_recipe, dict)
        else "Unknown"
    )

    notes: List[str] = []
    if not connected:
        notes.append("PLC communications are offline; the HMI is supervisory only until the link recovers.")
    if not runtime_ready:
        notes.append("The background automation poller is still warming up.")
    if supervisory_mode == "manual":
        notes.append("Manual mode is active. Automatic line start is intentionally blocked for commissioning work.")
    if supervisory_mode == "maintenance":
        notes.append("Maintenance mode is active. Production starts and recipe changes are locked out.")
    if safety_state == "WARNING":
        notes.append("A non-blocking safety warning is active; review alarms before pushing to full production.")
    if active_alarm_count:
        notes.append(f"{active_alarm_count} active alarm(s) need operator review.")
    if state == "STARTUP" and not (heaters_ready and die_ready):
        notes.append("Automatic startup is heating the barrel and die toward recipe setpoints.")
    if state == "RUNNING":
        notes.append("Automatic production is active; closed-loop control is managing feed, heat, and screw speed.")
    if state == "SHUTDOWN":
        notes.append("A controlled stop is in progress while the screw decelerates and the line cools safely.")
    if state == "EMERGENCY_STOP":
        notes.append("Safety chain is latched. Reset permissives and investigate alarms before restart.")
    if ready_for_start:
        notes.append("The line is thermally ready for an automatic production start.")
    if not notes:
        notes.append("Automation is standing by for operator action.")

    next_operator_action = "Review automation status"
    if state == "IDLE":
        if can_start:
            next_operator_action = "Start the automatic line sequence"
        elif supervisory_mode == "manual":
            next_operator_action = "Complete commissioning tasks or switch back to auto mode"
        elif supervisory_mode == "maintenance":
            next_operator_action = "Finish maintenance work and return the line to auto or manual mode"
        else:
            next_operator_action = "Restore permissives or PLC connectivity"
    elif state == "STARTUP":
        next_operator_action = "Monitor warm-up until the line reaches production readiness"
    elif state == "RUNNING":
        next_operator_action = "Supervise throughput, alarms, and recipe adherence"
    elif state == "SHUTDOWN":
        next_operator_action = "Wait for the controlled stop to complete"
    elif state == "EMERGENCY_STOP":
        next_operator_action = "Reset the safety chain and inspect the fault cause"

    return {
        "system_name": system_name,
        "system_type": "automated-extruder-system",
        "supervisory_mode": supervisory_mode,
        "lifecycle_phase": _AUTOMATION_PHASES.get(state, "unknown"),
        "ready_for_start": ready_for_start,
        "auto_sequence_active": auto_sequence_active,
        "plc_connected": connected,
        "runtime_ready": runtime_ready,
        "permissives_ok": permissives_ok,
        "heaters_ready": heaters_ready,
        "die_ready": die_ready,
        "can_start": can_start,
        "can_stop": can_stop,
        "can_reset": can_reset,
        "can_apply_recipe": can_apply_recipe,
        "active_recipe_name": active_recipe_name,
        "active_alarm_count": active_alarm_count,
        "next_operator_action": next_operator_action,
        "notes": notes,
    }
