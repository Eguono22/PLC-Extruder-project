"""Local entry point for the extruder application API."""

from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run("extruder_app.api:app", host="127.0.0.1", port=8000, reload=False)
