"""Pydantic models for the extruder application API."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ZoneSetpoints(BaseModel):
    """Temperature setpoints for barrel zones and the die."""

    barrel_c: List[float] = Field(
        default_factory=lambda: [180.0, 200.0, 220.0, 230.0],
        min_length=4,
        max_length=4,
    )
    die_c: float = Field(default=235.0, ge=0.0, le=450.0)


class RecipeDefinition(BaseModel):
    """Operator-facing recipe definition."""

    recipe_id: str
    name: str
    description: str
    feed_rate_kg_h: float = Field(ge=0.0, le=500.0)
    screw_rpm: float = Field(ge=0.0, le=250.0)
    zone_setpoints: ZoneSetpoints


class ActiveRecipeUpdate(BaseModel):
    """Request payload for applying a recipe."""

    recipe_id: Optional[str] = None
    name: Optional[str] = None
    description: str = ""
    feed_rate_kg_h: float = Field(default=50.0, ge=0.0, le=500.0)
    screw_rpm: float = Field(default=80.0, ge=0.0, le=250.0)
    zone_setpoints: ZoneSetpoints = Field(default_factory=ZoneSetpoints)


class AlarmItem(BaseModel):
    """Serializable alarm item."""

    code: str
    message: str
    severity: str
    timestamp: float
    acknowledged: bool


class EventItem(BaseModel):
    """Serializable application or control event."""

    ts: float
    type: str
    payload: Dict[str, object]


class ConnectionStatus(BaseModel):
    """PLC adapter connectivity and diagnostics snapshot."""

    plc_mode: str
    connected: bool
    endpoint: str
    node_prefix: str = ""
    last_error: str = ""
    last_poll_succeeded: bool = False


class OpcUaBrowseItem(BaseModel):
    """Single OPC UA browse result item."""

    node_id: str
    browse_name: str
    display_name: str
    node_class: str


class CommandResponse(BaseModel):
    """Simple response envelope for control commands."""

    ok: bool
    message: str


class RuntimeStatus(BaseModel):
    """Application runtime health and background polling state."""

    background_running: bool
    ready: bool
    sample_count: int
    event_count: int
    last_sample_ts: Optional[float] = None
    last_event_ts: Optional[float] = None


class HealthStatus(BaseModel):
    """Health check payload for liveness and readiness."""

    ok: bool
    status: str
    app_environment: str
    plc_mode: str
    plc_connected: bool
    runtime: RuntimeStatus


class AppMetadata(BaseModel):
    """Frontend metadata and deployment-facing app information."""

    app_name: str
    app_environment: str
    app_version: str
    plc_mode: str
    dashboard_refresh_ms: int


class OperationModeStatus(BaseModel):
    """Supervisory operating mode and mode-specific permissions."""

    mode: str
    available_modes: List[str]
    can_change_mode: bool
    automatic_commands_enabled: bool
    recipe_edits_enabled: bool
    maintenance_lockout: bool
    notes: List[str]


class OperationModeUpdate(BaseModel):
    """Request payload for changing the supervisory operating mode."""

    mode: str = Field(pattern="^(auto|manual|maintenance)$")


class TrendPoint(BaseModel):
    """Single time-series point for trend widgets."""

    ts: float
    state: str
    throughput_kg_h: float
    pressure_bar: float
    screw_rpm: float
    motor_current_a: float
    hopper_level_pct: float
    die_temp_c: float


class AnalyticsSummary(BaseModel):
    """Top-level analytics snapshot for dashboards and reports."""

    total_samples: int
    avg_throughput_kg_h: float
    max_pressure_bar: float
    avg_motor_current_a: float
    avg_die_temp_c: float
    runtime_s: float
    state: str
    active_alarm_count: int
    active_alarm_summary: str


class ProductionReport(BaseModel):
    """Aggregated production report for a recent sample window."""

    report_name: str
    generated_at: float
    window_samples: int
    plc_mode: str
    active_recipe_name: str
    runtime_s: float
    avg_throughput_kg_h: float
    peak_throughput_kg_h: float
    max_pressure_bar: float
    avg_motor_current_a: float
    avg_die_temp_c: float
    avg_hopper_level_pct: float
    event_count: int
    active_alarm_summary: str


class DashboardSnapshot(BaseModel):
    """Aggregated dashboard payload for the operator web UI."""

    machine: MachineStatus
    automation: "AutomationOverview"
    operation_mode: OperationModeStatus
    alarms: List[AlarmItem]
    analytics: AnalyticsSummary
    connection: ConnectionStatus
    events: List[EventItem]
    runtime: RuntimeStatus


class MachineStatus(BaseModel):
    """Operator-facing machine status."""

    state: str
    scan_number: int
    run_time_s: float
    recipe: Dict[str, float]
    safety: Dict[str, object]
    alarms: str
    heater: Dict[str, object]
    motor: Dict[str, object]
    feeder: Dict[str, object]
    die: Dict[str, object]
    plc_mode: str
    active_recipe: RecipeDefinition


class AutomationOverview(BaseModel):
    """High-level automation/HMI summary for the extruder system."""

    system_name: str
    system_type: str
    supervisory_mode: str
    lifecycle_phase: str
    ready_for_start: bool
    auto_sequence_active: bool
    plc_connected: bool
    runtime_ready: bool
    permissives_ok: bool
    heaters_ready: bool
    die_ready: bool
    can_start: bool
    can_stop: bool
    can_reset: bool
    can_apply_recipe: bool
    active_recipe_name: str
    active_alarm_count: int
    next_operator_action: str
    notes: List[str]


DashboardSnapshot.model_rebuild()
