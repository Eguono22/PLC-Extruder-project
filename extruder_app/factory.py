"""Application factory helpers."""

from __future__ import annotations

from extruder_app.logging_store import TelemetryStore
from extruder_app.plc_adapters import ModbusPlcAdapter, OpcUaPlcAdapter, SimulationPlcAdapter
from extruder_app.service import ExtruderApplicationService
from extruder_app.settings import AppSettings


def create_adapter(settings: AppSettings):
    """Create the PLC adapter based on configured mode."""
    if settings.plc_mode == "simulation":
        return SimulationPlcAdapter()
    if settings.plc_mode == "opcua":
        return OpcUaPlcAdapter(
            endpoint=settings.opcua_endpoint,
            node_prefix=settings.opcua_node_prefix,
            timeout_s=settings.opcua_timeout_s,
        )
    if settings.plc_mode == "modbus":
        return ModbusPlcAdapter(settings.modbus_endpoint)
    raise ValueError(
        "Unsupported EXTRUDER_PLC_MODE. Use one of: simulation, opcua, modbus."
    )


def create_service(settings: AppSettings) -> ExtruderApplicationService:
    """Create the full application service stack."""
    return ExtruderApplicationService(
        adapter=create_adapter(settings),
        telemetry=TelemetryStore(
            log_dir=settings.log_dir,
            persist_to_disk=settings.persist_logs,
        ),
        scan_interval_s=settings.scan_interval_s,
    )
