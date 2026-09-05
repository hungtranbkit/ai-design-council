"""FastAPI app factory for the AI Design Council web UI + API.

Run with: `python -m council serve` (see council/cli.py). Uses whatever
directory it's launched from as the runs/ root, matching the existing
`council run`/`compare` CLI convention.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from council.web.api import router as api_router
from council.web.pages import router as pages_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="AI Design Council", version="0.1.0")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(pages_router)
    app.include_router(api_router)
    return app


app = create_app()
