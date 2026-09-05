"""Private HTTP surface for the TradingAgents runtime.

This module intentionally does not import the vendored graph. Runtime settings
are validated first by the ASGI factory; graph construction begins in Task 3.
"""

from __future__ import annotations

from fastapi import FastAPI

from .config import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the private service after validating container-only settings."""

    runtime_settings = settings or load_settings()
    app = FastAPI(
        title="DataVest TradingAgents Service",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/internal/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "trading-agents",
            "stateRoot": str(runtime_settings.state_root),
        }

    return app
