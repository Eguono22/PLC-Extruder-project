"""Tests for commissioning helpers."""

from extruder_app.commissioning import (
    OpcUaSymbolCheck,
    prefixed_node_ids,
    summarize_symbol_checks,
)


def test_prefixed_node_ids_uses_configured_prefix():
    node_ids = prefixed_node_ids(
        "ns=4;s=",
        symbols=("gExtruderStatus.State", "gExtruderAI.Zone1Temp_C"),
    )
    assert node_ids == [
        "ns=4;s=gExtruderStatus.State",
        "ns=4;s=gExtruderAI.Zone1Temp_C",
    ]


def test_summarize_symbol_checks_reports_missing_and_samples():
    summary = summarize_symbol_checks(
        [
            OpcUaSymbolCheck(
                node_id="ns=2;s=gExtruderStatus.State",
                exists=True,
                readable=True,
                value_preview="'RUNNING'",
            ),
            OpcUaSymbolCheck(
                node_id="ns=2;s=gExtruderAI.Zone1Temp_C",
                exists=True,
                readable=False,
                value_preview="",
                error="Access denied",
            ),
            OpcUaSymbolCheck(
                node_id="ns=2;s=gExtruderCmd.Start",
                exists=False,
                readable=False,
                value_preview="",
                error="BadNodeIdUnknown",
            ),
        ]
    )

    assert "Checked 3 OPC UA symbols" in summary
    assert "Readable: 1" in summary
    assert "Unreadable: 1" in summary
    assert "Missing: 1" in summary
    assert "ns=2;s=gExtruderCmd.Start :: BadNodeIdUnknown" in summary
    assert "ns=2;s=gExtruderAI.Zone1Temp_C :: Access denied" in summary
    assert "ns=2;s=gExtruderStatus.State = 'RUNNING'" in summary
