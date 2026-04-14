"""Local entry point for the extruder application API."""

from __future__ import annotations

import uvicorn

from extruder_app.settings import AppSettings


if __name__ == "__main__":
    settings = AppSettings.from_env()
    uvicorn.run(
        "extruder_app.api:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
