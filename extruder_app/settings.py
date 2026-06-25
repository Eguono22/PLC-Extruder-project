"""Runtime settings for the extruder application."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


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


def _get_int_map(name: str, default: Dict[str, int]) -> Dict[str, int]:
    value = os.getenv(name)
    if value is None:
        return dict(default)
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError(f"{name} must be a JSON object.")
    result: Dict[str, int] = {}
    for key, item in loaded.items():
        result[str(key)] = int(item)
    merged = dict(default)
    merged.update(result)
    return merged


def _get_csv_list(name: str, default: List[str]) -> List[str]:
    value = os.getenv(name)
    if value is None:
        return list(default)
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or list(default)


@dataclass(frozen=True)
class AppSettings:
    """Environment-driven application settings."""

    DEFAULT_MODBUS_COMMAND_COIL_MAP = {
        "start": 0,
        "stop": 1,
        "reset": 2,
        "emergency_stop": 3,
        "acknowledge_alarms": 4,
    }
    DEFAULT_MODBUS_STATUS_REGISTER_MAP = {
        "state": 0,
        "scan_number_hi": 1,
        "scan_number_lo": 2,
        "run_time_hi": 3,
        "run_time_lo": 4,
        "safety_state": 5,
        "alarm_summary": 6,
        "flags": 7,
        "feed_rate_setpoint": 8,
        "screw_rpm_setpoint": 9,
        "zone1_sp": 10,
        "zone2_sp": 11,
        "zone3_sp": 12,
        "zone4_sp": 13,
        "die_sp": 14,
        "zone1_temp": 15,
        "zone2_temp": 16,
        "zone3_temp": 17,
        "zone4_temp": 18,
        "die_temp": 19,
        "pressure_bar": 20,
        "motor_rpm": 21,
        "motor_current": 22,
        "feeder_rate": 23,
        "hopper_level": 24,
    }
    DEFAULT_MODBUS_COMMAND_REGISTER_MAP = {
        "feed_rate_setpoint": 0,
        "screw_rpm_setpoint": 1,
        "zone1_sp": 2,
        "zone2_sp": 3,
        "zone3_sp": 4,
        "zone4_sp": 5,
        "die_sp": 6,
    }

    app_name: str = "Extruder Web Platform"
    app_environment: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    dashboard_refresh_ms: int = 1000
    static_cache_max_age_s: int = 3600
    cors_allowed_origins: List[str] = field(default_factory=list)
    trusted_hosts: List[str] = field(default_factory=lambda: ["*"])
    auth_enabled: bool = False
    auth_username: str = ""
    auth_password: str = ""
    auth_password_sha256: str = ""
    public_domain: str = "extruder.example.com"
    tls_email: str = ""
    plc_mode: str = "simulation"
    opcua_endpoint: str = "opc.tcp://127.0.0.1:4840"
    opcua_node_prefix: str = "ns=2;s="
    opcua_timeout_s: float = 5.0
    modbus_endpoint: str = "127.0.0.1:502"
    modbus_unit_id: int = 1
    modbus_timeout_s: float = 2.0
    modbus_command_coil_base: int = 0
    modbus_status_base_register: int = 1000
    modbus_command_base_register: int = 2000
    modbus_command_coil_map: Dict[str, int] = field(
        default_factory=lambda: dict(AppSettings.DEFAULT_MODBUS_COMMAND_COIL_MAP)
    )
    modbus_status_register_map: Dict[str, int] = field(
        default_factory=lambda: dict(AppSettings.DEFAULT_MODBUS_STATUS_REGISTER_MAP)
    )
    modbus_command_register_map: Dict[str, int] = field(
        default_factory=lambda: dict(AppSettings.DEFAULT_MODBUS_COMMAND_REGISTER_MAP)
    )
    scan_interval_s: float = 0.1
    persist_logs: bool = True
    log_dir: str = "runtime_logs"

    @property
    def auth_is_configured(self) -> bool:
        """Whether the configured auth settings are sufficient to enforce access control."""
        return bool(
            self.auth_username.strip()
            and (self.auth_password.strip() or self.auth_password_sha256.strip())
        )

    @property
    def auth_password_sha256_value(self) -> Optional[str]:
        """Normalized optional SHA-256 password digest."""
        value = self.auth_password_sha256.strip().lower()
        return value or None

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Build settings from environment variables."""
        return cls(
            app_name=os.getenv("EXTRUDER_APP_NAME", "Extruder Web Platform"),
            app_environment=os.getenv("EXTRUDER_APP_ENV", "development").strip().lower(),
            app_host=os.getenv("EXTRUDER_APP_HOST", "127.0.0.1"),
            app_port=_get_int("EXTRUDER_APP_PORT", 8000),
            dashboard_refresh_ms=_get_int("EXTRUDER_DASHBOARD_REFRESH_MS", 1000),
            static_cache_max_age_s=_get_int("EXTRUDER_STATIC_CACHE_MAX_AGE_S", 3600),
            cors_allowed_origins=_get_csv_list("EXTRUDER_CORS_ALLOWED_ORIGINS", []),
            trusted_hosts=_get_csv_list("EXTRUDER_TRUSTED_HOSTS", ["*"]),
            auth_enabled=_get_bool("EXTRUDER_AUTH_ENABLED", False),
            auth_username=os.getenv("EXTRUDER_AUTH_USERNAME", ""),
            auth_password=os.getenv("EXTRUDER_AUTH_PASSWORD", ""),
            auth_password_sha256=os.getenv("EXTRUDER_AUTH_PASSWORD_SHA256", ""),
            public_domain=os.getenv("EXTRUDER_PUBLIC_DOMAIN", "extruder.example.com"),
            tls_email=os.getenv("EXTRUDER_TLS_EMAIL", ""),
            plc_mode=os.getenv("EXTRUDER_PLC_MODE", "simulation").strip().lower(),
            opcua_endpoint=os.getenv("EXTRUDER_OPCUA_ENDPOINT", "opc.tcp://127.0.0.1:4840"),
            opcua_node_prefix=os.getenv("EXTRUDER_OPCUA_NODE_PREFIX", "ns=2;s="),
            opcua_timeout_s=_get_float("EXTRUDER_OPCUA_TIMEOUT_S", 5.0),
            modbus_endpoint=os.getenv("EXTRUDER_MODBUS_ENDPOINT", "127.0.0.1:502"),
            modbus_unit_id=_get_int("EXTRUDER_MODBUS_UNIT_ID", 1),
            modbus_timeout_s=_get_float("EXTRUDER_MODBUS_TIMEOUT_S", 2.0),
            modbus_command_coil_base=_get_int("EXTRUDER_MODBUS_COMMAND_COIL_BASE", 0),
            modbus_status_base_register=_get_int("EXTRUDER_MODBUS_STATUS_BASE_REGISTER", 1000),
            modbus_command_base_register=_get_int("EXTRUDER_MODBUS_COMMAND_BASE_REGISTER", 2000),
            modbus_command_coil_map=_get_int_map(
                "EXTRUDER_MODBUS_COMMAND_COIL_MAP_JSON",
                cls.DEFAULT_MODBUS_COMMAND_COIL_MAP,
            ),
            modbus_status_register_map=_get_int_map(
                "EXTRUDER_MODBUS_STATUS_REGISTER_MAP_JSON",
                cls.DEFAULT_MODBUS_STATUS_REGISTER_MAP,
            ),
            modbus_command_register_map=_get_int_map(
                "EXTRUDER_MODBUS_COMMAND_REGISTER_MAP_JSON",
                cls.DEFAULT_MODBUS_COMMAND_REGISTER_MAP,
            ),
            scan_interval_s=_get_float("EXTRUDER_SCAN_INTERVAL_S", 0.1),
            persist_logs=_get_bool("EXTRUDER_PERSIST_LOGS", True),
            log_dir=os.getenv("EXTRUDER_LOG_DIR", "runtime_logs"),
        )
