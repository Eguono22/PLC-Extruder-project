#!/usr/bin/env python3
"""Validate production-oriented environment settings for the extruder app."""

from __future__ import annotations

import sys

from extruder_app.production import validate_production_settings
from extruder_app.settings import AppSettings


def main() -> int:
    settings = AppSettings.from_env()
    result = validate_production_settings(settings)

    print("Extruder production preflight")
    print(f"Environment: {settings.app_environment}")
    print(f"Public domain: {settings.public_domain}")
    print(f"Auth enabled: {settings.auth_enabled}")
    print()

    if result.errors:
        print("Errors:")
        for item in result.errors:
            print(f"- {item}")
        print()

    if result.warnings:
        print("Warnings:")
        for item in result.warnings:
            print(f"- {item}")
        print()

    if result.ok:
        print("Configuration check passed.")
        return 0

    print("Configuration check failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
