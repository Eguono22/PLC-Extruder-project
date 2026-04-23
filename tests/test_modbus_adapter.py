"""Tests for Modbus adapter mapping helpers."""

from extruder_app.plc_adapters import ModbusPlcAdapter


class TestModbusAdapterHelpers:
    def test_parse_endpoint_supports_plain_host_port(self):
        host, port = ModbusPlcAdapter._parse_endpoint("192.168.0.50:1502")
        assert host == "192.168.0.50"
        assert port == 1502

    def test_build_snapshot_maps_register_values(self):
        adapter = ModbusPlcAdapter.__new__(ModbusPlcAdapter)
        adapter._cached_alarms = []
        registers = [
            2,      # state RUNNING
            0, 25,  # scan number
            0, 125, # runtime 12.5 s
            0,      # safety SAFE
            0,      # alarm word
            0b1100, # heater all at setpoint + die at setpoint
            500,    # feed rate sp
            800,    # screw rpm sp
            1800, 2000, 2200, 2300,
            2350,
            1800, 2000, 2200, 2300,
            2350,
            1100,
            800,
            350,
            500,
            820,
        ]

        snapshot = adapter._build_snapshot(registers)

        assert snapshot["state"] == "RUNNING"
        assert snapshot["scan_number"] == 25
        assert snapshot["run_time_s"] == 12.5
        assert snapshot["heater"]["all_at_setpoint"] is True
        assert snapshot["die"]["melt_pressure_bar"] == 110.0
        assert snapshot["motor"]["actual_rpm"] == 80.0
        assert snapshot["feeder"]["hopper_level_pct"] == 82.0
        assert snapshot["active_alarms"] == []

    def test_build_snapshot_creates_alarm_summary_when_flags_are_set(self):
        adapter = ModbusPlcAdapter.__new__(ModbusPlcAdapter)
        adapter._cached_alarms = []
        registers = [
            4,      # EMERGENCY_STOP
            0, 1,
            0, 10,
            3,      # E_STOP
            7,      # alarm word
            0b0011, # any alarm + any warning
            500,
            800,
            1800, 2000, 2200, 2300,
            2350,
            1800, 2000, 2200, 2300,
            2350,
            1100,
            800,
            350,
            500,
            820,
        ]

        snapshot = adapter._build_snapshot(registers)

        assert snapshot["state"] == "EMERGENCY_STOP"
        assert snapshot["active_alarms"][0]["code"] == "MODBUS_ALARM_SUMMARY"
        assert "AlarmWord 7" in snapshot["alarms"]

    def test_command_failure_returns_false_and_records_error(self):
        adapter = ModbusPlcAdapter.__new__(ModbusPlcAdapter)
        adapter._last_error = ""
        adapter._last_poll_succeeded = True
        adapter._connected = True

        def fail(_callback):
            raise RuntimeError("PLC offline")

        adapter._run_with_client = fail

        ok = adapter.start()

        assert ok is False
        assert adapter._connected is False
        assert adapter._last_poll_succeeded is False
        assert adapter._last_error == "PLC offline"
