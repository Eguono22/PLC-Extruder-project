"""CLI helper to validate the expected TwinCAT OPC UA symbol surface."""

from __future__ import annotations

import sys

from extruder_app.commissioning import (
    check_opcua_symbols_from_settings,
    summarize_symbol_checks,
)
from extruder_app.settings import AppSettings


def main() -> int:
    settings = AppSettings.from_env()
    try:
        results = check_opcua_symbols_from_settings(settings)
    except Exception as exc:
        print(f"OPC UA symbol check failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Commissioning target:",
        settings.opcua_endpoint,
        f"(prefix {settings.opcua_node_prefix})",
    )
    print()
    print(summarize_symbol_checks(results))
    return 0 if all(result.exists for result in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
