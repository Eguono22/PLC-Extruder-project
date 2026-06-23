"""Commissioning helpers for PLC connectivity checks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from extruder_app.settings import AppSettings

try:
    from asyncua import Client
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    Client = None


EXPECTED_OPCUA_SYMBOLS: Sequence[str] = (
    "gExtruderCmd.Start",
    "gExtruderCmd.Stop",
    "gExtruderCmd.Reset",
    "gExtruderCmd.EmergencyStop",
    "gExtruderCmd.RecipeFeedRateKgH",
    "gExtruderCmd.RecipeScrewRpm",
    "gExtruderCmd.Zone1Setpoint_C",
    "gExtruderCmd.Zone2Setpoint_C",
    "gExtruderCmd.Zone3Setpoint_C",
    "gExtruderCmd.Zone4Setpoint_C",
    "gExtruderCmd.DieSetpoint_C",
    "gExtruderStatus.State",
    "gExtruderStatus.RunTime_s",
    "gExtruderStatus.ScanNumber",
    "gExtruderStatus.ActiveRecipeName",
    "gExtruderStatus.SafetyState",
    "gExtruderStatus.AlarmSummary.AlarmWord",
    "gExtruderStatus.AnyAlarm",
    "gExtruderStatus.AnyWarning",
    "gExtruderStatus.HeaterAllAtSetpoint",
    "gExtruderStatus.DieAtSetpoint",
    "gExtruderStatus.FeedRateSetpointKgH",
    "gExtruderStatus.ScrewRpmSetpoint",
    "gExtruderStatus.Zone1Setpoint_C",
    "gExtruderStatus.Zone2Setpoint_C",
    "gExtruderStatus.Zone3Setpoint_C",
    "gExtruderStatus.Zone4Setpoint_C",
    "gExtruderStatus.DieSetpoint_C",
    "gExtruderAI.Zone1Temp_C",
    "gExtruderAI.Zone2Temp_C",
    "gExtruderAI.Zone3Temp_C",
    "gExtruderAI.Zone4Temp_C",
    "gExtruderAI.DieTemp_C",
    "gExtruderAI.MeltPressure_bar",
    "gExtruderAI.MotorRpm",
    "gExtruderAI.MotorCurrent_A",
    "gExtruderAI.FeederRateKgH",
    "gExtruderAI.HopperLevelPct",
)


@dataclass(frozen=True)
class OpcUaSymbolCheck:
    """Result of checking one expected OPC UA symbol."""

    node_id: str
    exists: bool
    readable: bool
    value_preview: str
    error: str = ""


def prefixed_node_ids(node_prefix: str, symbols: Iterable[str] = EXPECTED_OPCUA_SYMBOLS) -> List[str]:
    """Build fully qualified node ids from a configured prefix."""
    return [f"{node_prefix}{symbol}" for symbol in symbols]


async def check_opcua_symbols(
    endpoint: str,
    node_prefix: str,
    timeout_s: float = 5.0,
) -> List[OpcUaSymbolCheck]:
    """Connect to an OPC UA server and inspect the expected TwinCAT symbol set."""
    if Client is None:
        raise RuntimeError(
            "The asyncua package is required for OPC UA commissioning checks. "
            "Install dependencies from requirements.txt first."
        )

    client = Client(url=endpoint, timeout=timeout_s)
    try:
        await client.connect()
        results: List[OpcUaSymbolCheck] = []
        for node_id in prefixed_node_ids(node_prefix):
            node = client.get_node(node_id)
            try:
                await node.read_node_class()
            except Exception as exc:
                results.append(
                    OpcUaSymbolCheck(
                        node_id=node_id,
                        exists=False,
                        readable=False,
                        value_preview="",
                        error=str(exc),
                    )
                )
                continue

            try:
                value = await node.read_value()
                results.append(
                    OpcUaSymbolCheck(
                        node_id=node_id,
                        exists=True,
                        readable=True,
                        value_preview=_preview_value(value),
                    )
                )
            except Exception as exc:
                results.append(
                    OpcUaSymbolCheck(
                        node_id=node_id,
                        exists=True,
                        readable=False,
                        value_preview="",
                        error=str(exc),
                    )
                )
        return results
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def check_opcua_symbols_from_settings(settings: AppSettings) -> List[OpcUaSymbolCheck]:
    """Run the expected-symbol check using environment-backed app settings."""
    return asyncio.run(
        check_opcua_symbols(
            endpoint=settings.opcua_endpoint,
            node_prefix=settings.opcua_node_prefix,
            timeout_s=settings.opcua_timeout_s,
        )
    )


def summarize_symbol_checks(results: Sequence[OpcUaSymbolCheck]) -> str:
    """Render a compact text summary that is easy to scan in the terminal."""
    total = len(results)
    missing = [result for result in results if not result.exists]
    unreadable = [result for result in results if result.exists and not result.readable]
    readable = [result for result in results if result.exists and result.readable]

    lines = [
        f"Checked {total} OPC UA symbols",
        f"Readable: {len(readable)}",
        f"Unreadable: {len(unreadable)}",
        f"Missing: {len(missing)}",
    ]

    if missing:
        lines.append("")
        lines.append("Missing symbols:")
        for result in missing:
            lines.append(f"- {result.node_id} :: {result.error}")

    if unreadable:
        lines.append("")
        lines.append("Unreadable symbols:")
        for result in unreadable:
            lines.append(f"- {result.node_id} :: {result.error}")

    if readable:
        lines.append("")
        lines.append("Readable symbol samples:")
        for result in readable[:10]:
            preview = result.value_preview or "<empty>"
            lines.append(f"- {result.node_id} = {preview}")

    return "\n".join(lines)


def _preview_value(value: object) -> str:
    text = repr(value)
    if len(text) > 80:
        return text[:77] + "..."
    return text
