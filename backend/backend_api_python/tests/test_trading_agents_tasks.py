"""Celery dispatch contracts for the private TradingAgents service."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest


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


def test_resume_control_reuses_the_immutable_run_payload(monkeypatch):
    _install_task_dependencies()
    sys.modules.pop("app.tasks.trading_agents", None)
    from app.tasks import trading_agents as task_module

    class Repository:
        def get_run_for_worker(self, *, run_id):
            return {
                "run_id": run_id,
                "user_id": 7,
                "status": "queued",
                "event_sequence": 42,
                "request_json": json.dumps({
                    "market": "Crypto",
                    "symbol": "BTC/USDT",
                    "analysis_date": "2026-09-05",
                }),
                "config_json": json.dumps({"native_config": {"checkpoint_enabled": True}}),
            }

        def transition_run(self, **_kwargs):
            raise AssertionError("successful resume must not alter the run status")

    sent = []
    monkeypatch.setattr(task_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(task_module, "post_to_service", lambda **kwargs: sent.append(kwargs) or {"accepted": True})

    task_module.execute_trading_agents_control("run-123", "resume")

    assert sent == [{
        "path": "/internal/runs/run-123/resume",
        "payload": {
            "run_id": "run-123",
            "user_id": "7",
            "market": "Crypto",
            "symbol": "BTC/USDT",
            "analysis_date": "2026-09-05",
            "language": "vi-VN",
            "native_config": {"checkpoint_enabled": True},
            "selected_analysts": [],
            "event_sequence": 42,
        },
    }]


def test_vietnam_run_builds_persists_and_dispatches_evidence_once(monkeypatch):
    _install_task_dependencies()
    sys.modules.pop("app.tasks.trading_agents", None)
    from app.tasks import trading_agents as task_module

    evidence = {
        "version": "vietnam-evidence-v1",
        "asOf": "2026-09-16T16:59:59.999999+00:00",
        "instrument": {"market": "VNStock", "exchange": "HOSE", "symbol": "FPT"},
        "price": {"price": 123.0},
        "checksum": "a" * 64,
    }
    stored = []
    transitions = []

    class Repository:
        def get_run_for_worker(self, *, run_id):
            return {
                "run_id": run_id,
                "user_id": 7,
                "status": "queued",
                "request_json": {"market": "VNStock", "symbol": "FPT", "analysis_date": "2026-09-16"},
                "config_json": {"selected_analysts": ["market", "social", "news", "fundamentals"]},
                "evidence_json": None,
            }

        def store_evidence(self, *, run_id, evidence):
            stored.append((run_id, evidence))
            return evidence

        def transition_run(self, **kwargs):
            transitions.append(kwargs)

    sent = []
    monkeypatch.setattr(task_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(task_module, "build_trading_agents_vietnam_evidence", lambda symbol, analysis_date: evidence)
    monkeypatch.setattr(task_module, "post_to_service", lambda **kwargs: sent.append(kwargs) or {"accepted": True})

    task_module.execute_trading_agents_run("run-vn")

    assert stored == [("run-vn", evidence)]
    assert sent[0]["payload"]["vietnam_evidence"] == evidence
    assert transitions == [{"run_id": "run-vn", "status": "running"}]


def test_vietnam_resume_reuses_stored_evidence_without_provider_call(monkeypatch):
    _install_task_dependencies()
    sys.modules.pop("app.tasks.trading_agents", None)
    from app.tasks import trading_agents as task_module

    evidence = {
        "version": "vietnam-evidence-v1",
        "asOf": "2026-09-16T16:59:59.999999+00:00",
        "instrument": {"market": "VNStock", "exchange": "HOSE", "symbol": "FPT"},
        "price": {"price": 123.0},
        "checksum": "b" * 64,
    }

    class Repository:
        def get_run_for_worker(self, *, run_id):
            return {
                "run_id": run_id,
                "user_id": 7,
                "status": "queued",
                "event_sequence": 8,
                "request_json": {"market": "VNStock", "symbol": "FPT", "analysis_date": "2026-09-16"},
                "config_json": {"selected_analysts": ["market", "social", "news", "fundamentals"]},
                "evidence_json": json.dumps(evidence),
            }

        def transition_run(self, **_kwargs):
            raise AssertionError("successful resume must not alter run status")

        def store_evidence(self, **_kwargs):
            raise AssertionError("stored evidence must not be replaced")

    sent = []
    monkeypatch.setattr(task_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(
        task_module,
        "build_trading_agents_vietnam_evidence",
        lambda *_args: (_ for _ in ()).throw(AssertionError("provider must not be called")),
    )
    monkeypatch.setattr(task_module, "post_to_service", lambda **kwargs: sent.append(kwargs) or {"accepted": True})

    task_module.execute_trading_agents_control("run-vn", "resume")

    assert sent[0]["payload"]["vietnam_evidence"] == evidence


def test_vietnam_evidence_failure_marks_run_failed_without_dispatch(monkeypatch):
    _install_task_dependencies()
    sys.modules.pop("app.tasks.trading_agents", None)
    from app.tasks import trading_agents as task_module

    transitions = []

    class Repository:
        def get_run_for_worker(self, *, run_id):
            return {
                "run_id": run_id,
                "user_id": 7,
                "status": "queued",
                "request_json": {"market": "VNStock", "symbol": "FPT", "analysis_date": "2026-09-16"},
                "config_json": {},
                "evidence_json": None,
            }

        def transition_run(self, **kwargs):
            transitions.append(kwargs)

    monkeypatch.setattr(task_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(
        task_module,
        "build_trading_agents_vietnam_evidence",
        lambda *_args: (_ for _ in ()).throw(
            task_module.TradingAgentsVietnamEvidenceUnavailable("provider secret detail")
        ),
    )
    monkeypatch.setattr(
        task_module,
        "post_to_service",
        lambda **_kwargs: pytest.fail("invalid evidence must not be dispatched"),
    )

    task_module.execute_trading_agents_run("run-vn")

    assert transitions == [{
        "run_id": "run-vn",
        "status": "failed",
        "failure_code": "evidence_unavailable",
        "failure_message": "Vietnam evidence is unavailable for this TradingAgents run",
    }]


def test_artifact_fetch_signs_owner_scoped_body(monkeypatch):
    _install_task_dependencies()
    sys.modules.pop("app.tasks.trading_agents", None)
    from app.tasks import trading_agents as task_module

    class Response:
        headers = types.SimpleNamespace(get_content_type=lambda: "text/markdown")

        def read(self, _limit):
            return b"# Native report"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    sent = []
    monkeypatch.setenv("DATAVEST_TRADING_AGENTS_SERVICE_SECRET", "private-signing-secret")
    monkeypatch.setattr(task_module, "urlopen", lambda request, timeout: sent.append((request, timeout)) or Response())

    content, content_type = task_module.fetch_artifact_from_service(
        user_id=7,
        run_id="run-123",
        artifact_name="complete_report.md",
    )

    assert (content, content_type) == (b"# Native report", "text/markdown")
    request, _timeout = sent[0]
    assert request.full_url == "http://trading-agents:8080/internal/artifacts"
    assert json.loads(request.data.decode("utf-8")) == {
        "user_id": "7",
        "run_id": "run-123",
        "artifact_name": "complete_report.md",
    }
    assert "private-signing-secret" not in repr(request.headers)
