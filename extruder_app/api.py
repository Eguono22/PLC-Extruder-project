"""FastAPI application for the extruder machine operator panel."""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from extruder_app.factory import create_service
from extruder_app.models import (
    ActiveRecipeUpdate,
    AlarmItem,
    AnalyticsSummary,
    CommandResponse,
    ConnectionStatus,
    EventItem,
    MachineStatus,
    OpcUaBrowseItem,
    ProductionReport,
    RecipeDefinition,
    TrendPoint,
)
from extruder_app.settings import AppSettings


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Extruder AI Control System",
    version="0.1.0",
    description=(
        "Control, monitoring, alarms, and analytics API for an industrial "
        "extruder line."
    ),
)
settings = AppSettings.from_env()
service = create_service(settings)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def _startup() -> None:
    service.start_background()


@app.on_event("shutdown")
def _shutdown() -> None:
    service.stop_background()


@app.get("/", include_in_schema=False)
def operator_panel() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "plc_mode": service.plc_mode,
        "scan_interval_s": settings.scan_interval_s,
    }


@app.get("/api/connection", response_model=ConnectionStatus)
def get_connection_status() -> ConnectionStatus:
    return ConnectionStatus.model_validate(service.connection_status())


@app.get("/api/connection/browse", response_model=List[OpcUaBrowseItem])
def browse_connection_nodes(node_id: str = "") -> List[OpcUaBrowseItem]:
    items = service.browse_connection_nodes(node_id=node_id or None)
    return [OpcUaBrowseItem.model_validate(item) for item in items]


@app.get("/api/status", response_model=MachineStatus)
def get_status() -> MachineStatus:
    return MachineStatus.model_validate(service.machine_status())


@app.get("/api/recipes", response_model=List[RecipeDefinition])
def get_recipes() -> List[RecipeDefinition]:
    return service.recipes()


@app.get("/api/recipes/active", response_model=RecipeDefinition)
def get_active_recipe() -> RecipeDefinition:
    return service.active_recipe()


@app.put("/api/recipes/active", response_model=RecipeDefinition)
def set_active_recipe(recipe: ActiveRecipeUpdate) -> RecipeDefinition:
    return service.apply_recipe(recipe)


@app.get("/api/alarms", response_model=List[AlarmItem])
def get_alarms() -> List[AlarmItem]:
    return [AlarmItem.model_validate(item) for item in service.active_alarms()]


@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
def get_analytics_summary() -> AnalyticsSummary:
    return AnalyticsSummary.model_validate(service.analytics_summary())


@app.get("/api/events", response_model=List[EventItem])
def get_events(limit: int = 100) -> List[EventItem]:
    return [EventItem.model_validate(item) for item in service.recent_events(limit=limit)]


@app.get("/api/reports/production", response_model=ProductionReport)
def get_production_report(
    report_name: str = "Production Report",
    sample_limit: int = 500,
    event_limit: int = 200,
) -> ProductionReport:
    return ProductionReport.model_validate(
        service.production_report(
            report_name=report_name,
            sample_limit=sample_limit,
            event_limit=event_limit,
        )
    )


@app.get("/api/reports/production.csv", response_class=PlainTextResponse)
def get_production_report_csv(
    report_name: str = "Production Report",
    sample_limit: int = 500,
    event_limit: int = 200,
) -> str:
    return service.production_report_csv(
        report_name=report_name,
        sample_limit=sample_limit,
        event_limit=event_limit,
    )


@app.get("/api/trends/process", response_model=List[TrendPoint])
def get_process_trends(limit: int = 200) -> List[TrendPoint]:
    return [TrendPoint.model_validate(point) for point in service.trend_points(limit=limit)]


@app.post("/api/commands/start", response_model=CommandResponse)
def start_machine() -> CommandResponse:
    ok = service.start_machine()
    return CommandResponse(ok=ok, message="Start command processed")


@app.post("/api/commands/stop", response_model=CommandResponse)
def stop_machine() -> CommandResponse:
    ok = service.stop_machine()
    return CommandResponse(ok=ok, message="Stop command processed")


@app.post("/api/commands/reset", response_model=CommandResponse)
def reset_machine() -> CommandResponse:
    ok = service.reset_machine()
    return CommandResponse(ok=ok, message="Reset command processed")


@app.post("/api/commands/emergency-stop", response_model=CommandResponse)
def emergency_stop() -> CommandResponse:
    service.emergency_stop()
    return CommandResponse(ok=True, message="Emergency stop triggered")


@app.post("/api/commands/acknowledge-alarms", response_model=CommandResponse)
def acknowledge_alarms() -> CommandResponse:
    count = service.acknowledge_alarms()
    return CommandResponse(ok=True, message=f"Acknowledged {count} alarm(s)")
