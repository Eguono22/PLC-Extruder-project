"""Tests for production deployment helpers."""

from extruder_app.production import (
    DEFAULT_PASSWORD_PLACEHOLDER,
    sha256_password_digest,
    validate_production_settings,
)
from extruder_app.settings import AppSettings


def test_sha256_password_digest_is_stable():
    assert (
        sha256_password_digest("topsecret")
        == "53336a676c64c1396553b2b7c92f38126768827c93b64d9142069c10eda7a721"
    )


def test_validate_production_settings_reports_placeholder_password():
    settings = AppSettings(
        app_environment="production",
        auth_enabled=True,
        auth_username="operator",
        auth_password=DEFAULT_PASSWORD_PLACEHOLDER,
        public_domain="line.example.com",
        tls_email="ops@example.com",
    )

    result = validate_production_settings(settings)

    assert result.ok is False
    assert any("placeholder" in item for item in result.errors)


def test_validate_production_settings_warns_on_raw_password_and_wildcard_hosts():
    settings = AppSettings(
        app_environment="production",
        auth_enabled=True,
        auth_username="operator",
        auth_password="topsecret",
        public_domain="line.example.com",
        tls_email="ops@example.com",
        trusted_hosts=["*"],
    )

    result = validate_production_settings(settings)

    assert result.ok is True
    assert any("Prefer EXTRUDER_AUTH_PASSWORD_SHA256" in item for item in result.warnings)
    assert any("EXTRUDER_TRUSTED_HOSTS" in item for item in result.warnings)
