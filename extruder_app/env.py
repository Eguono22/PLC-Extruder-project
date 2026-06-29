"""Helpers for loading simple .env-style files."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: str | os.PathLike[str], *, override: bool = True) -> None:
    """Load KEY=VALUE pairs from a simple env file into ``os.environ``."""
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_path}")

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        if override or key not in os.environ:
            os.environ[key] = value
