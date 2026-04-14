"""Telemetry and event logging for the extruder application."""

from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional


class TelemetryStore:
    """Store recent telemetry and optionally persist it to disk."""

    def __init__(
        self,
        log_dir: str = "runtime_logs",
        max_samples: int = 5000,
        max_events: int = 1000,
        persist_to_disk: bool = True,
    ) -> None:
        self._samples: Deque[Dict[str, object]] = deque(maxlen=max_samples)
        self._events: Deque[Dict[str, object]] = deque(maxlen=max_events)
        self._persist_to_disk = persist_to_disk
        self._log_dir = Path(log_dir)
        self._telemetry_file = self._log_dir / "telemetry.jsonl"
        self._events_file = self._log_dir / "events.jsonl"
        if self._persist_to_disk:
            self._log_dir.mkdir(parents=True, exist_ok=True)

    def record_sample(self, snapshot: Dict[str, object]) -> None:
        """Append a machine snapshot."""
        sample = {"ts": time.time(), **snapshot}
        self._samples.append(sample)
        if self._persist_to_disk:
            with self._telemetry_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(sample) + "\n")

    def record_event(
        self, event_type: str, payload: Optional[Dict[str, object]] = None
    ) -> None:
        """Append a control or application event."""
        event = {
            "ts": time.time(),
            "type": event_type,
            "payload": payload or {},
        }
        self._events.append(event)
        if self._persist_to_disk:
            with self._events_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event) + "\n")

    def recent_samples(self, limit: int = 200) -> List[Dict[str, object]]:
        """Return the most recent telemetry samples."""
        return list(self._samples)[-limit:]

    def recent_events(self, limit: int = 100) -> List[Dict[str, object]]:
        """Return the most recent control events."""
        return list(self._events)[-limit:]

    def production_report(
        self,
        report_name: str,
        plc_mode: str,
        active_recipe_name: str,
        sample_limit: int = 500,
        event_limit: int = 200,
    ) -> Dict[str, object]:
        """Return an aggregated production report for recent activity."""
        samples = self.recent_samples(limit=sample_limit)
        events = self.recent_events(limit=event_limit)
        if not samples:
            return {
                "report_name": report_name,
                "generated_at": time.time(),
                "window_samples": 0,
                "plc_mode": plc_mode,
                "active_recipe_name": active_recipe_name,
                "runtime_s": 0.0,
                "avg_throughput_kg_h": 0.0,
                "peak_throughput_kg_h": 0.0,
                "max_pressure_bar": 0.0,
                "avg_motor_current_a": 0.0,
                "avg_die_temp_c": 0.0,
                "avg_hopper_level_pct": 0.0,
                "event_count": len(events),
                "active_alarm_summary": "No data",
            }

        def _avg(values: List[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        throughput = [float(s["die"]["throughput_kg_h"]) for s in samples]
        pressure = [float(s["die"]["melt_pressure_bar"]) for s in samples]
        motor_current = [float(s["motor"]["current_a"]) for s in samples]
        die_temp = [float(s["die"]["temperature_c"]) for s in samples]
        hopper_level = [float(s["feeder"]["hopper_level_pct"]) for s in samples]
        latest = samples[-1]

        return {
            "report_name": report_name,
            "generated_at": time.time(),
            "window_samples": len(samples),
            "plc_mode": plc_mode,
            "active_recipe_name": active_recipe_name,
            "runtime_s": float(latest["run_time_s"]),
            "avg_throughput_kg_h": round(_avg(throughput), 2),
            "peak_throughput_kg_h": round(max(throughput), 2),
            "max_pressure_bar": round(max(pressure), 2),
            "avg_motor_current_a": round(_avg(motor_current), 2),
            "avg_die_temp_c": round(_avg(die_temp), 2),
            "avg_hopper_level_pct": round(_avg(hopper_level), 2),
            "event_count": len(events),
            "active_alarm_summary": str(latest["alarms"]),
        }

    def analytics_summary(self) -> Dict[str, object]:
        """Return derived analytics from the recent sample window."""
        samples = list(self._samples)
        if not samples:
            return {
                "total_samples": 0,
                "avg_throughput_kg_h": 0.0,
                "max_pressure_bar": 0.0,
                "avg_motor_current_a": 0.0,
                "avg_die_temp_c": 0.0,
                "runtime_s": 0.0,
                "state": "IDLE",
                "active_alarm_count": 0,
                "active_alarm_summary": "No data",
            }

        def _avg(values: List[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        throughput = [float(s["die"]["throughput_kg_h"]) for s in samples]
        pressure = [float(s["die"]["melt_pressure_bar"]) for s in samples]
        motor_current = [float(s["motor"]["current_a"]) for s in samples]
        die_temp = [float(s["die"]["temperature_c"]) for s in samples]
        latest = samples[-1]

        return {
            "total_samples": len(samples),
            "avg_throughput_kg_h": round(_avg(throughput), 2),
            "max_pressure_bar": round(max(pressure), 2),
            "avg_motor_current_a": round(_avg(motor_current), 2),
            "avg_die_temp_c": round(_avg(die_temp), 2),
            "runtime_s": float(latest["run_time_s"]),
            "state": str(latest["state"]),
            "active_alarm_count": len(latest.get("active_alarms", [])),
            "active_alarm_summary": str(latest["alarms"]),
        }
