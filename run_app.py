"""Local entry point for the extruder application API."""

from __future__ import annotations

import uvicorn

from extruder_app.settings import AppSettings


if __name__ == "__main__":
    settings = AppSettings.from_env()
    uvicorn.run(
        "extruder_app.api:create_app",
        host=settings.app_host,
        port=settings.app_port,
        factory=True,
        forwarded_allow_ips="*",
        proxy_headers=True,
        reload=False,
    )
