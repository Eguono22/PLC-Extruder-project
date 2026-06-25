"""Tests for the production-facing FastAPI web application."""

import hashlib

from fastapi.testclient import TestClient

from extruder_app.api import create_app
from extruder_app.logging_store import TelemetryStore
from extruder_app.plc_adapters import SimulationPlcAdapter
from extruder_app.service import ExtruderApplicationService
from extruder_app.settings import AppSettings


def _make_client() -> TestClient:
    settings = AppSettings(
        app_name="Extruder Test Panel",
        app_environment="test",
        dashboard_refresh_ms=250,
        plc_mode="simulation",
    )
    service = ExtruderApplicationService(
        adapter=SimulationPlcAdapter(),
        telemetry=TelemetryStore(persist_to_disk=False),
        scan_interval_s=0.01,
    )
    return TestClient(create_app(settings=settings, service=service))


def _make_authenticated_client() -> TestClient:
    settings = AppSettings(
        app_name="Extruder Test Panel",
        app_environment="test",
        dashboard_refresh_ms=250,
        plc_mode="simulation",
        auth_enabled=True,
        auth_username="operator",
        auth_password_sha256=hashlib.sha256(b"topsecret").hexdigest(),
    )
    service = ExtruderApplicationService(
        adapter=SimulationPlcAdapter(),
        telemetry=TelemetryStore(persist_to_disk=False),
        scan_interval_s=0.01,
    )
    return TestClient(create_app(settings=settings, service=service))


def test_dashboard_endpoint_returns_aggregated_payload():
    with _make_client() as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["machine"]["plc_mode"] == "simulation"
    assert "analytics" in payload
    assert "runtime" in payload
    assert response.headers["cache-control"] == "no-store"


def test_meta_endpoint_exposes_frontend_configuration():
    with _make_client() as client:
        response = client.get("/api/meta")

    assert response.status_code == 200
    assert response.json() == {
        "app_name": "Extruder Test Panel",
        "app_environment": "test",
        "app_version": "1.0.0",
        "plc_mode": "simulation",
        "dashboard_refresh_ms": 250,
    }


def test_health_ready_reflects_runtime_state():
    with _make_client() as client:
        response = client.get("/api/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["runtime"]["background_running"] is True
    assert payload["plc_connected"] is True


def test_root_serves_web_application_with_security_headers():
    with _make_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Extruder Web Platform" in response.text
    assert response.headers["cache-control"] == "no-cache"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_protected_route_requires_basic_auth_when_enabled():
    with _make_authenticated_client() as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="Extruder Control"'


def test_protected_route_accepts_valid_basic_auth():
    with _make_authenticated_client() as client:
        response = client.get("/api/dashboard", auth=("operator", "topsecret"))

    assert response.status_code == 200
    assert response.json()["machine"]["plc_mode"] == "simulation"


def test_liveness_remains_public_when_auth_is_enabled():
    with _make_authenticated_client() as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_create_app_rejects_example_auth_password():
    settings = AppSettings(
        app_environment="production",
        auth_enabled=True,
        auth_username="operator",
        auth_password="change-this-password",
        public_domain="line.example.com",
        tls_email="ops@example.com",
    )
    service = ExtruderApplicationService(
        adapter=SimulationPlcAdapter(),
        telemetry=TelemetryStore(persist_to_disk=False),
        scan_interval_s=0.01,
    )

    try:
        create_app(settings=settings, service=service)
    except ValueError as exc:
        assert "example placeholder" in str(exc)
    else:
        raise AssertionError("Expected placeholder auth password to be rejected")
