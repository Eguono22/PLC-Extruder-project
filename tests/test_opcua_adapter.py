"""Tests for OPC UA adapter mapping helpers."""

from extruder_app.plc_adapters import OpcUaPlcAdapter


class TestOpcUaAdapterHelpers:
    def test_build_snapshot_maps_twincat_values(self):
        adapter = OpcUaPlcAdapter.__new__(OpcUaPlcAdapter)
        adapter._cached_alarms = []
        values = {
            "state": "RUNNING",
            "scan_number": 25,
            "run_time_s": 12.5,
            "safety_state": "SAFE",
            "alarm_summary": 0,
            "alarm_any": False,
            "alarm_warning": False,
            "heater_all_at_setpoint": True,
            "die_at_setpoint": True,
            "feed_rate_setpoint": 50.0,
            "screw_rpm_setpoint": 80.0,
            "zone1_sp": 180.0,
            "zone2_sp": 200.0,
            "zone3_sp": 220.0,
            "zone4_sp": 230.0,
            "die_sp": 235.0,
            "recipe_name": "Default Extrusion",
            "zone1_temp": 180.0,
            "zone2_temp": 200.0,
            "zone3_temp": 220.0,
            "zone4_temp": 230.0,
            "die_temp": 235.0,
            "pressure_bar": 110.0,
            "motor_rpm": 80.0,
            "motor_current": 35.0,
            "feeder_rate": 50.0,
            "hopper_level": 82.0,
        }

        snapshot = adapter._build_snapshot(values)

        assert snapshot["state"] == "RUNNING"
        assert snapshot["heater"]["all_at_setpoint"] is True
        assert snapshot["die"]["melt_pressure_bar"] == 110.0
        assert snapshot["motor"]["actual_rpm"] == 80.0

    def test_node_builder_uses_prefix(self):
        adapter = OpcUaPlcAdapter.__new__(OpcUaPlcAdapter)
        adapter.node_prefix = "ns=4;s="
        assert adapter._node("gExtruderStatus.State") == "ns=4;s=gExtruderStatus.State"

    def test_diagnostics_include_endpoint_and_prefix(self):
        adapter = OpcUaPlcAdapter.__new__(OpcUaPlcAdapter)
        adapter.endpoint = "opc.tcp://127.0.0.1:4840"
        adapter.node_prefix = "ns=2;s="
        adapter._last_poll_succeeded = True
        adapter._last_error = ""
        diagnostics = adapter.diagnostics()
        assert diagnostics["endpoint"] == "opc.tcp://127.0.0.1:4840"
        assert diagnostics["node_prefix"] == "ns=2;s="

    def test_browse_nodes_defaults_to_extruder_status(self):
        adapter = OpcUaPlcAdapter.__new__(OpcUaPlcAdapter)
        adapter.node_prefix = "ns=2;s="
        adapter._last_error = ""
        called = {}

        def fake_run(value):
            return value

        def fake_browse(node_id):
            called["node_id"] = node_id
            return [{"node_id": node_id}]

        adapter._run = fake_run
        adapter._browse = fake_browse

        items = adapter.browse_nodes()

        assert items == [{"node_id": "ns=2;s=gExtruderStatus"}]
        assert called["node_id"] == "ns=2;s=gExtruderStatus"
