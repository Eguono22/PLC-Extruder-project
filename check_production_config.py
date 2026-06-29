#!/usr/bin/env python3
"""Validate production-oriented environment settings for the extruder app."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from extruder_app.env import load_env_file
from extruder_app.production import validate_production_settings
from extruder_app.settings import AppSettings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate production-oriented environment settings for the extruder app.",
    )
    parser.add_argument(
        "--env-file",
        default=".env.production" if Path(".env.production").exists() else None,
        help="Optional env file to load before validation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.env_file:
        load_env_file(args.env_file)

    settings = AppSettings.from_env()
    result = validate_production_settings(settings)

    print("Extruder production preflight")
    if args.env_file:
        print(f"Env file: {args.env_file}")
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
