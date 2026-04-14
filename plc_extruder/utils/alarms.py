"""
Alarm management for the PLC Extruder platform.

Alarms are immutable records that can be acknowledged by the operator.
The :class:`AlarmManager` keeps an ordered log of all raised alarms and
exposes helpers used by the safety system and HMI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class AlarmSeverity(Enum):
    """Alarm priority levels (lowest → highest)."""
    INFO = auto()
    WARNING = auto()
    FAULT = auto()
    CRITICAL = auto()


@dataclass
class Alarm:
    """A single alarm event.

    Attributes:
        code: Short unique identifier (e.g. ``"OVER_TEMP_Z1"``).
        message: Human-readable description.
        severity: :class:`AlarmSeverity` level.
        timestamp: Unix time when the alarm was raised.
        acknowledged: True once an operator has acknowledged the alarm.
    """

    code: str
    message: str
    severity: AlarmSeverity
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False

    def acknowledge(self) -> None:
        """Mark this alarm as operator-acknowledged."""
        self.acknowledged = True

    def __str__(self) -> str:
        ack = "ACK" if self.acknowledged else "NEW"
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        return f"[{ts}] [{self.severity.name:8s}] [{ack}] {self.code}: {self.message}"


class AlarmManager:
    """Centralised alarm log and active-alarm registry.

    Usage::

        mgr = AlarmManager()
        mgr.raise_alarm("OVER_TEMP_Z1", "Zone 1 over temperature", AlarmSeverity.CRITICAL)
        mgr.acknowledge_alarm("OVER_TEMP_Z1")
    """

    def __init__(self) -> None:
        self._log: List[Alarm] = []
        self._active: dict[str, Alarm] = {}

    # ------------------------------------------------------------------
    # Alarm lifecycle
    # ------------------------------------------------------------------

    def raise_alarm(
        self,
        code: str,
        message: str,
        severity: AlarmSeverity,
    ) -> Alarm:
        """Raise a new alarm (no-op if the same code is already active).

        Args:
            code: Unique alarm code.
            message: Descriptive message.
            severity: Alarm priority level.

        Returns:
            The new (or existing active) :class:`Alarm` instance.
        """
        if code in self._active:
            return self._active[code]
        alarm = Alarm(code=code, message=message, severity=severity)
        self._active[code] = alarm
        self._log.append(alarm)
        return alarm

    def clear_alarm(self, code: str) -> None:
        """Remove an alarm from the active set (condition resolved).

        The alarm remains in the historical log.
        """
        self._active.pop(code, None)

    def acknowledge_alarm(self, code: str) -> bool:
        """Acknowledge an active alarm by its code.

        Returns:
            True if the alarm was found and acknowledged, False otherwise.
        """
        if code in self._active:
            self._active[code].acknowledge()
            return True
        return False

    def acknowledge_all(self) -> int:
        """Acknowledge every active alarm.

        Returns:
            Number of alarms acknowledged.
        """
        count = 0
        for alarm in self._active.values():
            if not alarm.acknowledged:
                alarm.acknowledge()
                count += 1
        return count

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def active_alarms(self) -> List[Alarm]:
        """List of currently active (uncleared) alarms."""
        return list(self._active.values())

    @property
    def unacknowledged_alarms(self) -> List[Alarm]:
        """Active alarms that have not yet been acknowledged."""
        return [a for a in self._active.values() if not a.acknowledged]

    @property
    def log(self) -> List[Alarm]:
        """Full historical alarm log (newest last)."""
        return list(self._log)

    def has_active(self, code: str) -> bool:
        """Return True if the given alarm code is currently active."""
        return code in self._active

    def highest_severity(self) -> Optional[AlarmSeverity]:
        """Return the highest severity among all active alarms, or None."""
        if not self._active:
            return None
        return max((a.severity for a in self._active.values()), key=lambda s: s.value)

    def is_any_critical(self) -> bool:
        """Return True if any active alarm has CRITICAL severity."""
        return any(
            a.severity == AlarmSeverity.CRITICAL for a in self._active.values()
        )

    def reset(self) -> None:
        """Clear all active alarms and wipe the historical log."""
        self._active.clear()
        self._log.clear()

    def summary(self) -> str:
        """Return a one-line summary string for the HMI status bar."""
        if not self._active:
            return "No active alarms"
        counts: dict[str, int] = {}
        for a in self._active.values():
            counts[a.severity.name] = counts.get(a.severity.name, 0) + 1
        parts = [f"{sev}: {n}" for sev, n in sorted(counts.items())]
        return "ALARMS – " + ", ".join(parts)

    def __repr__(self) -> str:
        return f"AlarmManager(active={len(self._active)}, log={len(self._log)})"
