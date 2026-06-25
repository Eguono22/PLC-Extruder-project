"""FastAPI application for the extruder machine operator panel."""

from __future__ import annotations

import base64
from contextlib import asynccontextmanager
import hashlib
from pathlib import Path
import secrets
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from extruder_app.factory import create_service
from extruder_app.models import (
    ActiveRecipeUpdate,
    AlarmItem,
    AnalyticsSummary,
    AppMetadata,
    CommandResponse,
    ConnectionStatus,
    DashboardSnapshot,
    EventItem,
    HealthStatus,
    MachineStatus,
    OpcUaBrowseItem,
    ProductionReport,
    RecipeDefinition,
    RuntimeStatus,
    TrendPoint,
)
from extruder_app.production import DEFAULT_PASSWORD_PLACEHOLDER
from extruder_app.service import ExtruderApplicationService
from extruder_app.settings import AppSettings


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
APP_VERSION = "1.0.0"
AUTH_EXEMPT_PATHS = {
    "/api/health",
    "/api/health/live",
    "/api/health/ready",
}


def _service(request: Request) -> ExtruderApplicationService:
    return request.app.state.service


def _settings(request: Request) -> AppSettings:
    return request.app.state.settings


def _command_result(ok: bool, accepted_message: str, rejected_message: str) -> CommandResponse:
    if not ok:
        raise HTTPException(status_code=503, detail=rejected_message)
    return CommandResponse(ok=True, message=accepted_message)


def _unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": "Authentication required"},
        headers={"WWW-Authenticate": 'Basic realm="Extruder Control"'},
    )


def _request_credentials(request: Request) -> Optional[tuple[str, str]]:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
    except Exception:
        return None
    username, separator, password = decoded.partition(":")
    if not separator:
        return None
    return username, password


def _credentials_match(settings: AppSettings, username: str, password: str) -> bool:
    if not secrets.compare_digest(username, settings.auth_username):
        return False
    configured_hash = settings.auth_password_sha256_value
    if configured_hash is not None:
        digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return secrets.compare_digest(digest, configured_hash)
    return secrets.compare_digest(password, settings.auth_password)


def _health_payload(settings: AppSettings, service: ExtruderApplicationService) -> HealthStatus:
    runtime = RuntimeStatus.model_validate(service.runtime_status())
    connection = service.connection_status()
    return HealthStatus(
        ok=runtime.ready,
        status="ready" if runtime.ready else "starting",
        app_environment=settings.app_environment,
        plc_mode=service.plc_mode,
        plc_connected=bool(connection["connected"]),
        runtime=runtime,
    )


def create_app(
    settings: Optional[AppSettings] = None,
    service: Optional[ExtruderApplicationService] = None,
) -> FastAPI:
    """Create the FastAPI application with lifecycle-managed services."""
    resolved_settings = settings or AppSettings.from_env()
    resolved_service = service or create_service(resolved_settings)
    if resolved_settings.auth_enabled and not resolved_settings.auth_is_configured:
        raise ValueError(
            "Authentication is enabled but EXTRUDER_AUTH_USERNAME and a password "
            "or EXTRUDER_AUTH_PASSWORD_SHA256 were not fully configured."
        )
    if resolved_settings.auth_enabled and resolved_settings.auth_password == DEFAULT_PASSWORD_PLACEHOLDER:
        raise ValueError(
            "Authentication is enabled but EXTRUDER_AUTH_PASSWORD is still set to the example placeholder."
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = resolved_settings
        app.state.service = resolved_service
        resolved_service.start_background()
        try:
            yield
        finally:
            resolved_service.stop_background()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=APP_VERSION,
        description=(
            "Control, monitoring, alarms, analytics, and commissioning API "
            "for an industrial extruder line."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(GZipMiddleware, minimum_size=512)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=resolved_settings.trusted_hosts)
    if resolved_settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.cors_allowed_origins,
            allow_methods=["GET", "POST", "PUT"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def add_response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'"
            ),
        )
        path = request.url.path
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif path.startswith("/static/"):
            response.headers["Cache-Control"] = (
                f"public, max-age={resolved_settings.static_cache_max_age_s}"
            )
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.middleware("http")
    async def require_basic_auth(request: Request, call_next):
        if not resolved_settings.auth_enabled or request.url.path in AUTH_EXEMPT_PATHS:
            return await call_next(request)
        credentials = _request_credentials(request)
        if credentials is None:
            return _unauthorized_response()
        username, password = credentials
        if not _credentials_match(resolved_settings, username, password):
            return _unauthorized_response()
        return await call_next(request)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def operator_panel() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/meta", response_model=AppMetadata)
    def get_app_metadata(request: Request) -> AppMetadata:
        settings = _settings(request)
        service = _service(request)
        return AppMetadata(
            app_name=settings.app_name,
            app_environment=settings.app_environment,
            app_version=APP_VERSION,
            plc_mode=service.plc_mode,
            dashboard_refresh_ms=settings.dashboard_refresh_ms,
        )

    @app.get("/api/health", response_model=HealthStatus)
    @app.get("/api/health/ready", response_model=HealthStatus)
    def readiness(request: Request) -> HealthStatus:
        settings = _settings(request)
        service = _service(request)
        return _health_payload(settings, service)

    @app.get("/api/health/live")
    def liveness(request: Request) -> dict:
        settings = _settings(request)
        service = _service(request)
        return {
            "ok": True,
            "status": "alive",
            "app_environment": settings.app_environment,
            "plc_mode": service.plc_mode,
        }

    @app.get("/api/runtime", response_model=RuntimeStatus)
    def get_runtime_status(request: Request) -> RuntimeStatus:
        return RuntimeStatus.model_validate(_service(request).runtime_status())

    @app.get("/api/connection", response_model=ConnectionStatus)
    def get_connection_status(request: Request) -> ConnectionStatus:
        return ConnectionStatus.model_validate(_service(request).connection_status())

    @app.get("/api/connection/browse", response_model=List[OpcUaBrowseItem])
    def browse_connection_nodes(request: Request, node_id: str = "") -> List[OpcUaBrowseItem]:
        items = _service(request).browse_connection_nodes(node_id=node_id or None)
        return [OpcUaBrowseItem.model_validate(item) for item in items]

    @app.get("/api/status", response_model=MachineStatus)
    def get_status(request: Request) -> MachineStatus:
        return MachineStatus.model_validate(_service(request).machine_status())

    @app.get("/api/dashboard", response_model=DashboardSnapshot)
    def get_dashboard(request: Request, event_limit: int = 12) -> DashboardSnapshot:
        return DashboardSnapshot.model_validate(
            _service(request).dashboard_snapshot(event_limit=event_limit)
        )

    @app.get("/api/recipes", response_model=List[RecipeDefinition])
    def get_recipes(request: Request) -> List[RecipeDefinition]:
        return _service(request).recipes()

    @app.get("/api/recipes/active", response_model=RecipeDefinition)
    def get_active_recipe(request: Request) -> RecipeDefinition:
        return _service(request).active_recipe()

    @app.put("/api/recipes/active", response_model=RecipeDefinition)
    def set_active_recipe(request: Request, recipe: ActiveRecipeUpdate) -> RecipeDefinition:
        return _service(request).apply_recipe(recipe)

    @app.get("/api/alarms", response_model=List[AlarmItem])
    def get_alarms(request: Request) -> List[AlarmItem]:
        return [AlarmItem.model_validate(item) for item in _service(request).active_alarms()]

    @app.get("/api/analytics/summary", response_model=AnalyticsSummary)
    def get_analytics_summary(request: Request) -> AnalyticsSummary:
        return AnalyticsSummary.model_validate(_service(request).analytics_summary())

    @app.get("/api/events", response_model=List[EventItem])
    def get_events(request: Request, limit: int = 100) -> List[EventItem]:
        return [
            EventItem.model_validate(item)
            for item in _service(request).recent_events(limit=limit)
        ]

    @app.get("/api/reports/production", response_model=ProductionReport)
    def get_production_report(
        request: Request,
        report_name: str = "Production Report",
        sample_limit: int = 500,
        event_limit: int = 200,
    ) -> ProductionReport:
        return ProductionReport.model_validate(
            _service(request).production_report(
                report_name=report_name,
                sample_limit=sample_limit,
                event_limit=event_limit,
            )
        )

    @app.get("/api/reports/production.csv", response_class=PlainTextResponse)
    def get_production_report_csv(
        request: Request,
        report_name: str = "Production Report",
        sample_limit: int = 500,
        event_limit: int = 200,
    ) -> PlainTextResponse:
        csv_text = _service(request).production_report_csv(
            report_name=report_name,
            sample_limit=sample_limit,
            event_limit=event_limit,
        )
        return PlainTextResponse(
            csv_text,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    'attachment; filename="extruder-production-report.csv"'
                )
            },
        )

    @app.get("/api/trends/process", response_model=List[TrendPoint])
    def get_process_trends(request: Request, limit: int = 200) -> List[TrendPoint]:
        return [
            TrendPoint.model_validate(point)
            for point in _service(request).trend_points(limit=limit)
        ]

    @app.post("/api/commands/start", response_model=CommandResponse)
    def start_machine(request: Request) -> CommandResponse:
        return _command_result(
            _service(request).start_machine(),
            accepted_message="Start command processed",
            rejected_message="Start command rejected by the active PLC adapter",
        )

    @app.post("/api/commands/stop", response_model=CommandResponse)
    def stop_machine(request: Request) -> CommandResponse:
        return _command_result(
            _service(request).stop_machine(),
            accepted_message="Stop command processed",
            rejected_message="Stop command rejected by the active PLC adapter",
        )

    @app.post("/api/commands/reset", response_model=CommandResponse)
    def reset_machine(request: Request) -> CommandResponse:
        return _command_result(
            _service(request).reset_machine(),
            accepted_message="Reset command processed",
            rejected_message="Reset command rejected by the active PLC adapter",
        )

    @app.post("/api/commands/emergency-stop", response_model=CommandResponse)
    def emergency_stop(request: Request) -> CommandResponse:
        _service(request).emergency_stop()
        return CommandResponse(ok=True, message="Emergency stop triggered")

    @app.post("/api/commands/acknowledge-alarms", response_model=CommandResponse)
    def acknowledge_alarms(request: Request) -> CommandResponse:
        count = _service(request).acknowledge_alarms()
        return CommandResponse(ok=True, message=f"Acknowledged {count} alarm(s)")

    return app


app = create_app()
