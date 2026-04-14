#!/usr/bin/env python3
"""
PLC Extruder Platform – main entry point.

Launches an interactive simulation that walks through the full extrusion
cycle: startup (heat soak), production run, and controlled shutdown.
Run without arguments for an automated demo::

    python main.py

Or supply a duration and recipe via flags::

    python main.py --run-time 300 --feed-rate 60 --screw-rpm 90
"""

from __future__ import annotations

import argparse
import sys
import time

from plc_extruder.controller import ExtruderController, ControllerState
import config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PLC Industrial Extruder Simulation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--run-time",
        type=float,
        default=600.0,
        metavar="SECONDS",
        help="Target production run time in simulated seconds",
    )
    parser.add_argument(
        "--feed-rate",
        type=float,
        default=50.0,
        metavar="KG_H",
        help="Material feed rate (kg/h)",
    )
    parser.add_argument(
        "--screw-rpm",
        type=float,
        default=80.0,
        metavar="RPM",
        help="Extruder screw speed (RPM)",
    )
    parser.add_argument(
        "--status-interval",
        type=int,
        default=500,
        metavar="SCANS",
        help="Print status every N scan cycles",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colour output",
    )
    return parser.parse_args()


def colorize(text: str, code: str, no_color: bool = False) -> str:
    """Wrap *text* in an ANSI colour escape unless *no_color* is True."""
    if no_color:
        return text
    return f"\033[{code}m{text}\033[0m"


def run_simulation(args: argparse.Namespace) -> None:
    """Execute the full extruder simulation loop."""
    nc = args.no_color

    print(colorize("=" * 60, "1;34", nc))
    print(colorize("  PLC INDUSTRIAL EXTRUDER PLATFORM", "1;34", nc))
    print(colorize("  Simulation starting…", "1;34", nc))
    print(colorize("=" * 60, "1;34", nc))
    print(f"  Recipe  : feed={args.feed_rate} kg/h, RPM={args.screw_rpm}")
    print(f"  Run time: {args.run_time} s (simulated)")
    print(f"  Scan dt : {config.SCAN_CYCLE_S * 1000:.0f} ms")
    print()

    ctrl = ExtruderController()
    ctrl.set_recipe(feed_rate=args.feed_rate, screw_rpm=args.screw_rpm)

    # ------------------------------------------------------------------ #
    # STARTUP                                                              #
    # ------------------------------------------------------------------ #
    print(colorize("[1/3] Starting up – heating all barrel zones…", "33", nc))
    ctrl.start()

    startup_scans = 0
    max_startup_scans = 30_000  # 3000 s max warm-up time at 0.1 s/scan
    while ctrl.state == ControllerState.STARTUP and startup_scans < max_startup_scans:
        ctrl.scan()
        startup_scans += 1
        if startup_scans % args.status_interval == 0:
            temps = [f"{z.temperature:.0f}" for z in ctrl.heater.zones]
            print(
                f"  Startup scan {startup_scans:>5}: "
                f"zones [{', '.join(temps)}] °C  "
                f"die={ctrl.die.temperature:.0f} °C"
            )

    if ctrl.state != ControllerState.RUNNING:
        print(
            colorize(
                f"  ERROR: Failed to reach RUNNING state "
                f"(state={ctrl.state.name})",
                "31",
                nc,
            )
        )
        _print_active_alarms(ctrl, nc)
        sys.exit(1)

    print(colorize("  All zones at setpoint – production started.", "32", nc))
    print()

    # ------------------------------------------------------------------ #
    # PRODUCTION RUN                                                       #
    # ------------------------------------------------------------------ #
    print(colorize("[2/3] Production run…", "33", nc))
    target_scans = int(args.run_time / config.SCAN_CYCLE_S)
    prod_scans = 0

    while ctrl.state == ControllerState.RUNNING and prod_scans < target_scans:
        ctrl.scan()
        prod_scans += 1
        if prod_scans % args.status_interval == 0:
            d = ctrl.die
            m = ctrl.motor
            f = ctrl.feeder
            print(
                f"  [{ctrl.run_time_s:6.0f} s]  "
                f"RPM={m.actual_rpm:5.1f}  "
                f"Q={d.throughput_kg_h:5.1f} kg/h  "
                f"P={d.melt_pressure_bar:5.1f} bar  "
                f"Hopper={f.hopper_level_pct:.0f}%  "
                f"{ctrl.alarms.summary()}"
            )

    if ctrl.state == ControllerState.EMERGENCY_STOP:
        print(colorize("  *** EMERGENCY STOP ***", "1;31", nc))
        _print_active_alarms(ctrl, nc)
        sys.exit(1)

    print(
        colorize(
            f"  Production run complete – {ctrl.run_time_s:.0f} s, "
            f"{ctrl.die.throughput_kg_h:.1f} kg/h",
            "32",
            nc,
        )
    )
    print()

    # ------------------------------------------------------------------ #
    # SHUTDOWN                                                             #
    # ------------------------------------------------------------------ #
    print(colorize("[3/3] Controlled shutdown…", "33", nc))
    ctrl.stop()
    shutdown_scans = 0
    max_shutdown = 5000

    while ctrl.state == ControllerState.SHUTDOWN and shutdown_scans < max_shutdown:
        ctrl.scan()
        shutdown_scans += 1

    if ctrl.state == ControllerState.IDLE:
        print(colorize("  Shutdown complete – system IDLE.", "32", nc))
    else:
        print(
            colorize(
                f"  Shutdown did not complete (state={ctrl.state.name})", "31", nc
            )
        )

    # Final status report
    print()
    print(ctrl.format_status())


def _print_active_alarms(ctrl: ExtruderController, nc: bool) -> None:
    """Print all active alarms to stdout."""
    alarms = ctrl.alarms.active_alarms
    if alarms:
        print(colorize("  Active alarms:", "1;31", nc))
        for a in alarms:
            print(f"    {a}")


def main() -> None:
    args = parse_args()
    run_simulation(args)


if __name__ == "__main__":
    main()
