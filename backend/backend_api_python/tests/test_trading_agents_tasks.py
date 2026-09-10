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


def test_completed_report_generates_summary_before_pdf_export(monkeypatch):
    _install_task_dependencies()
    sys.modules.pop("app.tasks.trading_agents", None)
    from app.tasks import trading_agents as task_module

    report = b"# BTC research\n\n## Market analysis\nNative report content."
    stored = []

    class Repository:
        def get_run_for_worker(self, *, run_id):
            assert run_id == "run-123"
            return {
                "run_id": run_id,
                "user_id": 7,
                "status": "succeeded",
                "request_json": {"language": "vi-VN"},
                "config_json": {"report_summary_generation": "async-v1"},
            }

        def get_owned_run(self, *, user_id, run_id):
            assert (user_id, run_id) == (7, "run-123")
            return {
                "artifacts": [{
                    "artifact_name": "complete_report.md",
                    "sha256": __import__("hashlib").sha256(report).hexdigest(),
                }],
            }

        def get_report_summary(self, **_kwargs):
            return None

        def store_report_summary(self, **kwargs):
            stored.append(kwargs)

    monkeypatch.setattr(task_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(task_module, "fetch_artifact_from_service", lambda **_kwargs: (report, "text/markdown"))
    monkeypatch.setattr(
        task_module,
        "generate_report_summary",
        lambda **_kwargs: {"overview": "Tóm tắt đã lưu trước khi xuất PDF."},
        raising=False,
    )

    task_module.execute_trading_agents_report_summary("run-123")

    assert stored == [{
        "user_id": 7,
        "run_id": "run-123",
        "source_sha256": __import__("hashlib").sha256(report).hexdigest(),
        "language": "vi-VN",
        "summary": {"overview": "Tóm tắt đã lưu trước khi xuất PDF."},
    }]
