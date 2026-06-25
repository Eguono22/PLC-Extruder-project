"""Production deployment helpers for auth and configuration checks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import List

from extruder_app.settings import AppSettings


DEFAULT_PASSWORD_PLACEHOLDER = "change-this-password"
DEFAULT_DOMAIN_PLACEHOLDER = "extruder.example.com"


def sha256_password_digest(password: str) -> str:
    """Return a SHA-256 hex digest for a plaintext password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProductionValidationResult:
    """Outcome of validating environment-driven production settings."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether the configuration is safe enough to proceed."""
        return not self.errors


def validate_production_settings(settings: AppSettings) -> ProductionValidationResult:
    """Validate deployment settings and return actionable errors and warnings."""
    errors: List[str] = []
    warnings: List[str] = []

    if settings.auth_enabled:
        if not settings.auth_username.strip():
            errors.append("Authentication is enabled but EXTRUDER_AUTH_USERNAME is empty.")
        if not settings.auth_is_configured:
            errors.append(
                "Authentication is enabled but no valid password or SHA-256 digest is configured."
            )
        if settings.auth_password == DEFAULT_PASSWORD_PLACEHOLDER:
            errors.append(
                "EXTRUDER_AUTH_PASSWORD is still using the example placeholder value."
            )
        if settings.auth_password and not settings.auth_password_sha256_value:
            warnings.append(
                "EXTRUDER_AUTH_PASSWORD is set directly. Prefer EXTRUDER_AUTH_PASSWORD_SHA256 for production."
            )
    elif settings.app_environment == "production":
        warnings.append(
            "Authentication is disabled in production. Only do this on a strictly private network."
        )

    if settings.app_environment == "production":
        if settings.public_domain.strip() == DEFAULT_DOMAIN_PLACEHOLDER:
            errors.append(
                "EXTRUDER_PUBLIC_DOMAIN is still set to the example domain placeholder."
            )
        if not settings.tls_email.strip():
            errors.append(
                "EXTRUDER_TLS_EMAIL must be set in production so the reverse proxy can manage certificates."
            )
        if settings.trusted_hosts == ["*"]:
            warnings.append(
                "EXTRUDER_TRUSTED_HOSTS is set to '*'. Restrict it to your real hostnames in production."
            )
        if settings.cors_allowed_origins:
            insecure_origins = [
                origin for origin in settings.cors_allowed_origins if origin.startswith("http://")
            ]
            if insecure_origins:
                warnings.append(
                    "Some CORS origins use http:// instead of https://: "
                    + ", ".join(insecure_origins)
                )

    return ProductionValidationResult(errors=errors, warnings=warnings)
