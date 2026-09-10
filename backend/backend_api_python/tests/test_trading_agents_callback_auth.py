"""Security contracts for the private TradingAgents callback boundary."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from flask import Flask


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _enable_lightweight_app_imports() -> None:
    """Avoid booting unrelated Flask routes in this callback-boundary test."""
    if "app" not in sys.modules:
        package = types.ModuleType("app")
        package.__path__ = [str(BACKEND_ROOT / "app")]
        sys.modules["app"] = package
    if "app.utils" not in sys.modules:
        utils_package = types.ModuleType("app.utils")
        utils_package.__path__ = [str(BACKEND_ROOT / "app" / "utils")]
        sys.modules["app.utils"] = utils_package


def _client_with_callback(secret: str = "not-a-real-secret"):
    _enable_lightweight_app_imports()
    from app.services.trading_agents import (
        TradingAgentsCallbackService,
        create_internal_callback_blueprint,
    )

    class Repository:
        def __init__(self):
            self.events = []

        def append_event(self, **event):
            self.events.append(event)

    repository = Repository()
    service = TradingAgentsCallbackService(
        repository=repository,
        secret=secret,
        now=lambda: 1_788_832_400,
    )
    app = Flask(__name__)
    app.register_blueprint(create_internal_callback_blueprint(lambda: service))
    return app.test_client(), repository, service


def test_callback_rejects_invalid_signature():
    client, repository, _service = _client_with_callback()

    response = client.post(
        "/api/internal/trading-agents/callback",
        json={"run_id": "run-123", "sequence": 1, "event_type": "agent_started", "payload": {}},
    )

    assert response.status_code == 401
    assert repository.events == []
    assert response.get_json()["error"]["code"] == "UNAUTHORIZED"


def test_callback_persists_only_redacted_payload_after_valid_signature():
    client, repository, service = _client_with_callback()
    body = json.dumps(
        {
            "run_id": "run-123",
            "sequence": 4,
            "event_type": "tool",
            "payload": {
                "provider": "yfinance",
                "api_key": "must-not-be-stored",
                "headers": {"Authorization": "must-not-be-stored"},
                "traceback": "must-not-be-stored",
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")
    timestamp = "1788832400"

    response = client.post(
        "/api/internal/trading-agents/callback",
        data=body,
        content_type="application/json",
        headers={
            "X-DataVest-Trading-Agents-Timestamp": timestamp,
            "X-DataVest-Trading-Agents-Signature": service.sign(timestamp=timestamp, body=body),
        },
    )

    assert response.status_code == 202
    assert repository.events == [{
        "run_id": "run-123",
        "sequence": 4,
        "event_type": "tool",
        "payload": {
            "provider": "yfinance",
            "api_key": "[REDACTED]",
            "headers": "[REDACTED]",
            "traceback": "[REDACTED]",
        },
    }]


def test_succeeded_callback_queues_the_report_summary_in_background(monkeypatch):
    _enable_lightweight_app_imports()
    from app.services import trading_agents as callback_module

    queued = []
    monkeypatch.setattr(callback_module, "enqueue_report_summary", lambda run_id: queued.append(run_id), raising=False)

    class Repository:
        def append_event(self, **_event):
            return None

        def transition_run(self, **_transition):
            return None

    service = callback_module.TradingAgentsCallbackService(
        repository=Repository(),
        secret="not-a-real-secret",
        now=lambda: 1_788_832_400,
    )
    body = json.dumps(
        {
            "run_id": "run-123",
            "sequence": 9,
            "event_type": "run_status",
            "payload": {"status": "succeeded"},
        },
        separators=(",", ":"),
    ).encode("utf-8")

    service.persist_callback(
        headers={
            "X-DataVest-Trading-Agents-Timestamp": "1788832400",
            "X-DataVest-Trading-Agents-Signature": service.sign(timestamp="1788832400", body=body),
        },
        raw_body=body,
    )

    assert queued == ["run-123"]
