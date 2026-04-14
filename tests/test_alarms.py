"""Unit tests for the alarm manager."""

import pytest
from plc_extruder.utils.alarms import AlarmManager, Alarm, AlarmSeverity


class TestAlarm:
    def test_str_contains_code(self):
        a = Alarm(code="TEST_001", message="Test alarm", severity=AlarmSeverity.WARNING)
        assert "TEST_001" in str(a)

    def test_acknowledge(self):
        a = Alarm(code="X", message="m", severity=AlarmSeverity.INFO)
        assert not a.acknowledged
        a.acknowledge()
        assert a.acknowledged


class TestAlarmManager:
    def _mgr(self) -> AlarmManager:
        return AlarmManager()

    def test_raise_alarm_adds_to_active(self):
        mgr = self._mgr()
        mgr.raise_alarm("A1", "msg", AlarmSeverity.INFO)
        assert mgr.has_active("A1")
        assert len(mgr.active_alarms) == 1

    def test_raise_same_code_is_idempotent(self):
        mgr = self._mgr()
        a1 = mgr.raise_alarm("A1", "msg", AlarmSeverity.INFO)
        a2 = mgr.raise_alarm("A1", "msg2", AlarmSeverity.WARNING)
        assert a1 is a2
        assert len(mgr.active_alarms) == 1

    def test_clear_alarm(self):
        mgr = self._mgr()
        mgr.raise_alarm("A1", "msg", AlarmSeverity.FAULT)
        mgr.clear_alarm("A1")
        assert not mgr.has_active("A1")
        assert len(mgr.active_alarms) == 0

    def test_clear_nonexistent_alarm_is_safe(self):
        mgr = self._mgr()
        mgr.clear_alarm("NONEXISTENT")  # should not raise

    def test_acknowledge_alarm(self):
        mgr = self._mgr()
        mgr.raise_alarm("A1", "msg", AlarmSeverity.WARNING)
        result = mgr.acknowledge_alarm("A1")
        assert result is True
        assert mgr.active_alarms[0].acknowledged

    def test_acknowledge_nonexistent_returns_false(self):
        mgr = self._mgr()
        assert mgr.acknowledge_alarm("GHOST") is False

    def test_acknowledge_all(self):
        mgr = self._mgr()
        mgr.raise_alarm("A1", "m1", AlarmSeverity.INFO)
        mgr.raise_alarm("A2", "m2", AlarmSeverity.WARNING)
        count = mgr.acknowledge_all()
        assert count == 2
        assert all(a.acknowledged for a in mgr.active_alarms)

    def test_unacknowledged_alarms(self):
        mgr = self._mgr()
        mgr.raise_alarm("A1", "m", AlarmSeverity.INFO)
        mgr.raise_alarm("A2", "m", AlarmSeverity.WARNING)
        mgr.acknowledge_alarm("A1")
        unacked = mgr.unacknowledged_alarms
        assert len(unacked) == 1
        assert unacked[0].code == "A2"

    def test_highest_severity_none_when_empty(self):
        mgr = self._mgr()
        assert mgr.highest_severity() is None

    def test_highest_severity(self):
        mgr = self._mgr()
        mgr.raise_alarm("A1", "m", AlarmSeverity.INFO)
        mgr.raise_alarm("A2", "m", AlarmSeverity.CRITICAL)
        mgr.raise_alarm("A3", "m", AlarmSeverity.WARNING)
        assert mgr.highest_severity() == AlarmSeverity.CRITICAL

    def test_is_any_critical(self):
        mgr = self._mgr()
        assert not mgr.is_any_critical()
        mgr.raise_alarm("A1", "m", AlarmSeverity.CRITICAL)
        assert mgr.is_any_critical()

    def test_log_persists_cleared_alarms(self):
        mgr = self._mgr()
        mgr.raise_alarm("A1", "m", AlarmSeverity.INFO)
        mgr.clear_alarm("A1")
        assert len(mgr.log) == 1
        assert not mgr.has_active("A1")

    def test_reset_clears_everything(self):
        mgr = self._mgr()
        mgr.raise_alarm("A1", "m", AlarmSeverity.FAULT)
        mgr.reset()
        assert len(mgr.active_alarms) == 0
        assert len(mgr.log) == 0

    def test_summary_no_alarms(self):
        mgr = self._mgr()
        assert mgr.summary() == "No active alarms"

    def test_summary_with_alarms(self):
        mgr = self._mgr()
        mgr.raise_alarm("A1", "m", AlarmSeverity.CRITICAL)
        summary = mgr.summary()
        assert "CRITICAL" in summary

    def test_repr(self):
        mgr = self._mgr()
        assert "AlarmManager" in repr(mgr)
