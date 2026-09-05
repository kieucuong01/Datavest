"""Celery dispatch contracts for the private TradingAgents service."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _install_task_dependencies() -> None:
    if "app" not in sys.modules:
        package = types.ModuleType("app")
        package.__path__ = [str(BACKEND_ROOT / "app")]
        sys.modules["app"] = package
    if "app.services" not in sys.modules:
        package = types.ModuleType("app.services")
        package.__path__ = [str(BACKEND_ROOT / "app" / "services")]
        sys.modules["app.services"] = package

    celery_module = types.ModuleType("app.celery_app")

    class Celery:
        def task(self, **_kwargs):
            return lambda function: function

    celery_module.celery_app = Celery()
    sys.modules["app.celery_app"] = celery_module


def test_run_dispatch_signs_private_service_request_without_returning_secret(monkeypatch):
    _install_task_dependencies()
    sys.modules.pop("app.tasks.trading_agents", None)
    from app.tasks import trading_agents as task_module

    class Repository:
        def get_run_for_worker(self, *, run_id):
            assert run_id == "run-123"
            return {
                "run_id": run_id,
                "user_id": 7,
                "status": "queued",
                "request_json": json.dumps({
                    "market": "Crypto",
                    "symbol": "BTC/USDT",
                    "analysis_date": "2026-09-05",
                }),
                "config_json": json.dumps({"native_config": {"quick_think_llm": "deepseek-chat"}}),
            }

        def transition_run(self, **_kwargs):
            return None

        def append_event(self, **_kwargs):
            return None

    sent = []

    class Response:
        def read(self, _limit):
            return b'{"accepted":true}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        sent.append((request, timeout))
        return Response()

    monkeypatch.setenv("DATAVEST_TRADING_AGENTS_SERVICE_SECRET", "private-signing-secret")
    monkeypatch.setattr(task_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(task_module, "urlopen", fake_urlopen)

    task_module.execute_trading_agents_run("run-123")

    assert len(sent) == 1
    request, _timeout = sent[0]
    assert request.full_url == "http://trading-agents:8080/internal/runs"
    assert json.loads(request.data.decode("utf-8"))["run_id"] == "run-123"
    assert json.loads(request.data.decode("utf-8"))["user_id"] == "7"
    assert request.get_header("X-datavest-trading-agents-request-signature") != "private-signing-secret"
    assert "private-signing-secret" not in repr(request.headers)
