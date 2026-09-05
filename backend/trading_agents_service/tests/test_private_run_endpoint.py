from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from fastapi.testclient import TestClient


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.main import _signature, create_app


def _settings() -> Settings:
    return Settings(
        callback_secret="callback-secret-123",
        service_secret="service-secret-123",
        callback_url="http://backend:5000/api/internal/trading-agents/callback",
        state_root=PurePosixPath("/var/lib/tradingagents"),
        upstream_env=MappingProxyType({}),
        host="0.0.0.0",
        port=8080,
    )


def test_private_run_endpoint_rejects_unsigned_request():
    client = TestClient(create_app(_settings()))

    response = client.post("/internal/runs", json={"run_id": "run-123"})

    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized"


def test_private_run_endpoint_accepts_signed_request_without_running_inline(monkeypatch):
    from app import main as main_module

    starts = []

    class Thread:
        def __init__(self, **kwargs):
            starts.append(kwargs)

        def start(self):
            return None

    monkeypatch.setattr(main_module.threading, "Thread", Thread)
    settings = _settings()
    client = TestClient(create_app(settings))
    payload = {
        "run_id": "run-123",
        "user_id": "7",
        "market": "Crypto",
        "symbol": "BTC/USDT",
        "analysis_date": "2026-09-05",
        "selected_analysts": ["market", "social", "news", "fundamentals"],
        "native_config": {},
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = "1788832400"
    monkeypatch.setattr(main_module.time, "time", lambda: int(timestamp))

    response = client.post(
        "/internal/runs",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-DataVest-Trading-Agents-Request-Timestamp": timestamp,
            "X-DataVest-Trading-Agents-Request-Signature": _signature(settings.service_secret, timestamp, body),
        },
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "run_id": "run-123"}
    assert len(starts) == 1
