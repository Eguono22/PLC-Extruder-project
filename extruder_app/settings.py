"""Runtime settings for the extruder application."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


@dataclass(frozen=True)
class AppSettings:
    """Environment-driven application settings."""

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    plc_mode: str = "simulation"
    opcua_endpoint: str = "opc.tcp://127.0.0.1:4840"
    opcua_node_prefix: str = "ns=2;s="
    opcua_timeout_s: float = 5.0
    modbus_endpoint: str = "127.0.0.1:502"
    scan_interval_s: float = 0.1
    persist_logs: bool = True
    log_dir: str = "runtime_logs"

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Build settings from environment variables."""
        return cls(
            app_host=os.getenv("EXTRUDER_APP_HOST", "127.0.0.1"),
            app_port=_get_int("EXTRUDER_APP_PORT", 8000),
            plc_mode=os.getenv("EXTRUDER_PLC_MODE", "simulation").strip().lower(),
            opcua_endpoint=os.getenv("EXTRUDER_OPCUA_ENDPOINT", "opc.tcp://127.0.0.1:4840"),
            opcua_node_prefix=os.getenv("EXTRUDER_OPCUA_NODE_PREFIX", "ns=2;s="),
            opcua_timeout_s=_get_float("EXTRUDER_OPCUA_TIMEOUT_S", 5.0),
            modbus_endpoint=os.getenv("EXTRUDER_MODBUS_ENDPOINT", "127.0.0.1:502"),
            scan_interval_s=_get_float("EXTRUDER_SCAN_INTERVAL_S", 0.1),
            persist_logs=_get_bool("EXTRUDER_PERSIST_LOGS", True),
            log_dir=os.getenv("EXTRUDER_LOG_DIR", "runtime_logs"),
        )
