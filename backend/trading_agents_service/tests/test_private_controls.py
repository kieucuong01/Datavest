from __future__ import annotations

import json
import sys
from pathlib import Path
from types import MappingProxyType

from fastapi.testclient import TestClient


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings
from app.main import _signature, create_app


def _settings(state_root: Path) -> Settings:
    return Settings(
        callback_secret="callback-secret-123",
        service_secret="service-secret-123",
        callback_url="http://backend:5000/api/internal/trading-agents/callback",
        state_root=state_root,
        upstream_env=MappingProxyType({}),
        host="0.0.0.0",
        port=8080,
    )


def _signed_post(client: TestClient, settings: Settings, path: str, payload: dict, monkeypatch):
    from app import main as main_module

    timestamp = "1788832400"
    monkeypatch.setattr(main_module.time, "time", lambda: int(timestamp))
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return client.post(
        path,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-DataVest-Trading-Agents-Request-Timestamp": timestamp,
            "X-DataVest-Trading-Agents-Request-Signature": _signature(settings.service_secret, timestamp, body),
        },
    )


def _payload() -> dict:
    return {
        "run_id": "run-123",
        "user_id": "7",
        "market": "Crypto",
        "symbol": "BTC/USDT",
        "analysis_date": "2026-09-05",
        "selected_analysts": ["market", "social", "news", "fundamentals"],
        "native_config": {"checkpoint_enabled": True},
    }


def test_cancel_marks_the_active_run_without_accepting_unsigned_control(tmp_path: Path, monkeypatch) -> None:
    from app import main as main_module

    starts = []

    class Thread:
        def __init__(self, **kwargs):
            starts.append(kwargs)

        def start(self):
            return None

    monkeypatch.setattr(main_module.threading, "Thread", Thread)
    settings = _settings(tmp_path)
    client = TestClient(create_app(settings))

    assert _signed_post(client, settings, "/internal/runs", _payload(), monkeypatch).status_code == 202
    assert client.post("/internal/runs/run-123/cancel", json=_payload()).status_code == 401

    response = _signed_post(client, settings, "/internal/runs/run-123/cancel", _payload(), monkeypatch)

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "run_id": "run-123", "status": "cancellation_requested"}
    assert len(starts) == 1


def test_artifact_endpoint_reads_only_the_callers_scoped_run_directory(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    report = tmp_path / "users" / "7" / "results" / "reports" / "runs" / "run-123" / "complete_report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# Native report", encoding="utf-8")
    client = TestClient(create_app(settings))

    response = _signed_post(
        client,
        settings,
        "/internal/artifacts",
        {"user_id": "7", "run_id": "run-123", "artifact_name": "complete_report.md"},
        monkeypatch,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.content == b"# Native report"

    traversal = _signed_post(
        client,
        settings,
        "/internal/artifacts",
        {"user_id": "7", "run_id": "run-123", "artifact_name": "../memory/trading_memory.md"},
        monkeypatch,
    )
    assert traversal.status_code == 422


def test_clear_checkpoint_uses_the_pinned_upstream_lifecycle(tmp_path: Path, monkeypatch) -> None:
    from app import main as main_module

    cleared = []
    monkeypatch.setattr(main_module, "clear_native_checkpoint", lambda request, **kwargs: cleared.append((request, kwargs)))
    settings = _settings(tmp_path)
    client = TestClient(create_app(settings))

    response = _signed_post(client, settings, "/internal/runs/run-123/clear-checkpoint", _payload(), monkeypatch)

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "run_id": "run-123", "status": "checkpoint_cleared"}
    assert cleared[0][0].run_id == "run-123"
    assert cleared[0][1]["state_root"] == tmp_path
