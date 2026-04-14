"""High-level application service for the extruder line."""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

from extruder_app.logging_store import TelemetryStore
from extruder_app.models import ActiveRecipeUpdate, RecipeDefinition, ZoneSetpoints
from extruder_app.plc_adapters import BasePlcAdapter, SimulationPlcAdapter


class ExtruderApplicationService:
    """Owns the active machine source, recipes, logging, and background scans."""

    def __init__(
        self,
        adapter: Optional[BasePlcAdapter] = None,
        telemetry: Optional[TelemetryStore] = None,
        scan_interval_s: float = 0.1,
    ) -> None:
        self._adapter = adapter or SimulationPlcAdapter()
        self._telemetry = telemetry or TelemetryStore()
        self._scan_interval_s = scan_interval_s
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._recipes = self._build_default_recipes()
        self._active_recipe = self._recipes["general-purpose"]
        self.apply_recipe(
            ActiveRecipeUpdate(
                recipe_id=self._active_recipe.recipe_id,
                name=self._active_recipe.name,
                description=self._active_recipe.description,
                feed_rate_kg_h=self._active_recipe.feed_rate_kg_h,
                screw_rpm=self._active_recipe.screw_rpm,
                zone_setpoints=self._active_recipe.zone_setpoints,
            )
        )

    @property
    def plc_mode(self) -> str:
        """Current PLC integration mode."""
        return self._adapter.mode_name

    def start_background(self) -> None:
        """Start the background scan loop."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._telemetry.record_event("app_started", {"plc_mode": self.plc_mode})

    def stop_background(self) -> None:
        """Stop the background scan loop."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._telemetry.record_event("app_stopped", {"plc_mode": self.plc_mode})

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.poll_once()
            time.sleep(self._scan_interval_s)

    def poll_once(self) -> Dict[str, object]:
        """Perform one scan/poll and persist the resulting snapshot."""
        with self._lock:
            self._adapter.scan()
            snapshot = self._adapter.status_snapshot()
            self._telemetry.record_sample(snapshot)
            return snapshot

    def recipes(self) -> List[RecipeDefinition]:
        """Return built-in recipes."""
        return list(self._recipes.values())

    def active_recipe(self) -> RecipeDefinition:
        """Return the currently applied recipe."""
        return self._active_recipe

    def apply_recipe(self, recipe: ActiveRecipeUpdate) -> RecipeDefinition:
        """Apply a built-in or custom recipe."""
        with self._lock:
            if recipe.recipe_id and recipe.recipe_id in self._recipes:
                selected = self._recipes[recipe.recipe_id]
            else:
                selected = RecipeDefinition(
                    recipe_id=recipe.recipe_id or "custom",
                    name=recipe.name or "Custom Recipe",
                    description=recipe.description or "Operator-defined process settings",
                    feed_rate_kg_h=recipe.feed_rate_kg_h,
                    screw_rpm=recipe.screw_rpm,
                    zone_setpoints=recipe.zone_setpoints,
                )

            self._adapter.set_recipe(
                feed_rate_kg_h=selected.feed_rate_kg_h,
                screw_rpm=selected.screw_rpm,
                zone_setpoints_c=selected.zone_setpoints.barrel_c,
                die_setpoint_c=selected.zone_setpoints.die_c,
            )
            self._active_recipe = selected
            self._telemetry.record_event(
                "recipe_applied",
                {
                    "recipe_id": selected.recipe_id,
                    "feed_rate_kg_h": selected.feed_rate_kg_h,
                    "screw_rpm": selected.screw_rpm,
                },
            )
            return selected

    def start_machine(self) -> bool:
        with self._lock:
            result = self._adapter.start()
            self._telemetry.record_event("start_command", {"accepted": result})
            return result

    def stop_machine(self) -> bool:
        with self._lock:
            result = self._adapter.stop()
            self._telemetry.record_event("stop_command", {"accepted": result})
            return result

    def reset_machine(self) -> bool:
        with self._lock:
            result = self._adapter.reset()
            self._telemetry.record_event("reset_command", {"accepted": result})
            return result

    def emergency_stop(self) -> None:
        with self._lock:
            self._adapter.emergency_stop()
            self._telemetry.record_event("emergency_stop", {"accepted": True})

    def acknowledge_alarms(self) -> int:
        with self._lock:
            count = self._adapter.acknowledge_alarms()
            self._telemetry.record_event("acknowledge_alarms", {"count": count})
            return count

    def machine_status(self) -> Dict[str, object]:
        """Return the latest machine snapshot enriched for the app layer."""
        with self._lock:
            snapshot = self._adapter.status_snapshot()
            snapshot["plc_mode"] = self.plc_mode
            snapshot["active_recipe"] = self._active_recipe.dict()
            return snapshot

    def active_alarms(self) -> List[Dict[str, object]]:
        """Return serialized active alarms."""
        with self._lock:
            return [
                {
                    "code": alarm.code,
                    "message": alarm.message,
                    "severity": alarm.severity.name,
                    "timestamp": alarm.timestamp,
                    "acknowledged": alarm.acknowledged,
                }
                for alarm in self._adapter.active_alarms()
            ]

    def trend_points(self, limit: int = 200) -> List[Dict[str, object]]:
        """Return recent samples reshaped for graphing."""
        points = []
        for sample in self._telemetry.recent_samples(limit=limit):
            points.append(
                {
                    "ts": sample["ts"],
                    "state": sample["state"],
                    "throughput_kg_h": sample["die"]["throughput_kg_h"],
                    "pressure_bar": sample["die"]["melt_pressure_bar"],
                    "screw_rpm": sample["motor"]["actual_rpm"],
                    "motor_current_a": sample["motor"]["current_a"],
                    "hopper_level_pct": sample["feeder"]["hopper_level_pct"],
                    "die_temp_c": sample["die"]["temperature_c"],
                }
            )
        return points

    def analytics_summary(self) -> Dict[str, object]:
        """Return aggregate process analytics."""
        return self._telemetry.analytics_summary()

    @staticmethod
    def _build_default_recipes() -> Dict[str, RecipeDefinition]:
        return {
            "general-purpose": RecipeDefinition(
                recipe_id="general-purpose",
                name="General Purpose",
                description="Balanced default settings for commissioning and demos",
                feed_rate_kg_h=50.0,
                screw_rpm=80.0,
                zone_setpoints=ZoneSetpoints(
                    barrel_c=[180.0, 200.0, 220.0, 230.0],
                    die_c=235.0,
                ),
            ),
            "hdpe-pipe": RecipeDefinition(
                recipe_id="hdpe-pipe",
                name="HDPE Pipe",
                description="Higher throughput profile for HDPE pipe extrusion",
                feed_rate_kg_h=62.0,
                screw_rpm=92.0,
                zone_setpoints=ZoneSetpoints(
                    barrel_c=[175.0, 195.0, 210.0, 220.0],
                    die_c=225.0,
                ),
            ),
            "pvc-profile": RecipeDefinition(
                recipe_id="pvc-profile",
                name="PVC Profile",
                description="Lower-temperature profile suited to PVC processing",
                feed_rate_kg_h=42.0,
                screw_rpm=58.0,
                zone_setpoints=ZoneSetpoints(
                    barrel_c=[165.0, 178.0, 186.0, 192.0],
                    die_c=195.0,
                ),
            ),
        }
