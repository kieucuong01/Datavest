from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath
from types import MappingProxyType


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.main import create_app


def test_health_is_private_and_does_not_expose_credentials() -> None:
    app = create_app(
        Settings(
            callback_secret="internal-only",
            service_secret="private-service-only",
            callback_url="http://backend:5000/api/internal/trading-agents/callback",
            state_root=PurePosixPath("/var/lib/tradingagents"),
            upstream_env=MappingProxyType({"DEEPSEEK_API_KEY": "must-not-leak"}),
            host="0.0.0.0",
            port=8080,
        )
    )

    health = next(route for route in app.routes if route.path == "/internal/health")

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
    assert health.endpoint() == {
        "status": "ok",
        "service": "trading-agents",
        "stateRoot": "/var/lib/tradingagents",
    }
