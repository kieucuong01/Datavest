"""Owner-scoped public TradingAgents gateway contracts."""

from __future__ import annotations

import hashlib
import sys
import types
from functools import wraps
from pathlib import Path

from flask import Blueprint as FlaskBlueprint
from flask import Flask, g


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _install_route_dependencies() -> None:
    if "app" not in sys.modules:
        package = types.ModuleType("app")
        package.__path__ = [str(BACKEND_ROOT / "app")]
        sys.modules["app"] = package
    if "app.utils" not in sys.modules:
        package = types.ModuleType("app.utils")
        package.__path__ = [str(BACKEND_ROOT / "app" / "utils")]
        sys.modules["app.utils"] = package
    if "app.openapi" not in sys.modules:
        package = types.ModuleType("app.openapi")
        package.__path__ = [str(BACKEND_ROOT / "app" / "openapi")]
        sys.modules["app.openapi"] = package

    blueprint_module = types.ModuleType("app.openapi.blueprint")
    blueprint_module.HumanBlueprint = FlaskBlueprint
    sys.modules["app.openapi.blueprint"] = blueprint_module

    auth_module = types.ModuleType("app.utils.auth")

    def login_required(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            g.user_id = 7
            return function(*args, **kwargs)

        return wrapped

    auth_module.login_required = login_required
    sys.modules["app.utils.auth"] = auth_module

    tasks_module = types.ModuleType("app.tasks.trading_agents")
    class TradingAgentsServiceUnavailable(RuntimeError):
        pass

    tasks_module.TradingAgentsServiceUnavailable = TradingAgentsServiceUnavailable
    tasks_module.enqueue_trading_agents_run = types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
    tasks_module.enqueue_trading_agents_control = types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
    tasks_module.fetch_artifact_from_service = lambda **_kwargs: (b"", "text/plain")
    sys.modules["app.tasks.trading_agents"] = tasks_module


def _client(monkeypatch):
    _install_route_dependencies()
    sys.modules.pop("app.routes.trading_agents", None)
    from app.routes import trading_agents as route_module

    app = Flask(__name__)
    app.register_blueprint(route_module.trading_agents_blp, url_prefix="/api/trading-agents")
    return app.test_client(), route_module


def test_user_cannot_read_another_users_run(monkeypatch):
    client, route_module = _client(monkeypatch)

    class Repository:
        def get_owned_run(self, **_kwargs):
            return None

    monkeypatch.setattr(route_module, "get_repository", lambda: Repository())

    response = client.get("/api/trading-agents/runs/other-users-run")

    assert response.status_code == 404
    assert response.get_json()["data"] is None


def test_run_history_is_filtered_to_the_current_owner_asset_and_day(monkeypatch):
    client, route_module = _client(monkeypatch)
    calls = []

    class Repository:
        def list_owned_runs(self, **kwargs):
            calls.append(kwargs)
            return [{
                "run_id": "run-123",
                "status": "succeeded",
                "request_json": {
                    "market": "Crypto",
                    "symbol": "BTC/USDT",
                    "analysis_date": "2026-09-05",
                },
                "source_pin": "9dee508",
            }]

    monkeypatch.setattr(route_module, "get_repository", lambda: Repository())

    response = client.get(
        "/api/trading-agents/runs?market=Crypto&symbol=BTC%2FUSDT&analysisDate=2026-09-05&limit=1"
    )

    assert response.status_code == 200
    assert calls == [{
        "user_id": 7,
        "market": "Crypto",
        "symbol": "BTC/USDT",
        "analysis_date": "2026-09-05",
        "limit": 1,
    }]
    public_run = response.get_json()["data"]["runs"][0]
    assert public_run["run_id"] == "run-123"
    assert public_run["status"] == "succeeded"
    assert public_run["market"] == "Crypto"
    assert public_run["symbol"] == "BTC/USDT"
    assert public_run["analysis_date"] == "2026-09-05"
    assert public_run["source_pin"] == "9dee508"
    assert public_run["events"] == []
    assert public_run["progress"]["percent"] < 100


def test_create_reuses_an_exact_active_run_for_repeated_clicks(monkeypatch):
    client, route_module = _client(monkeypatch)
    created = []

    class Repository:
        def get_active_run(self, **kwargs):
            assert kwargs == {
                "user_id": 7,
                "market": "Crypto",
                "symbol": "BTC/USDT",
                "analysis_date": "2026-09-05",
            }
            return {"run_id": "already-running", "status": "running"}

        def create_run(self, **kwargs):
            created.append(kwargs)
            raise AssertionError("an active exact run must be reused")

    monkeypatch.setattr(route_module, "get_repository", lambda: Repository())

    response = client.post(
        "/api/trading-agents/runs",
        json={"market": "Crypto", "symbol": "BTC/USDT", "analysisDate": "2026-09-05"},
    )

    assert response.status_code == 202
    assert response.get_json()["data"] == {
        "run_id": "already-running",
        "status": "running",
        "reused": True,
    }
    assert created == []


def test_event_stream_exposes_progress_metadata_without_raw_model_payload(monkeypatch):
    client, route_module = _client(monkeypatch)

    class Repository:
        def get_owned_run(self, **_kwargs):
            return {
                "run_id": "run-123",
                "status": "succeeded",
                "events": [{
                    "sequence": 1,
                    "event_type": "upstream_chunk",
                    "created_at": "2026-09-05T00:00:00+00:00",
                    "payload_json": {
                        "stage_id": "market",
                        "market_report": "private report body",
                    },
                }],
            }

    monkeypatch.setattr(route_module, "get_repository", lambda: Repository())

    response = client.get("/api/trading-agents/runs/run-123/events")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert '"stage_id": "market"' in body
    assert "private report body" not in body


def test_run_is_queued_without_exposing_service_secret(monkeypatch):
    client, route_module = _client(monkeypatch)
    queued = []

    class Repository:
        def create_run(self, **kwargs):
            assert kwargs["user_id"] == 7
            assert kwargs["request"]["market"] == "Crypto"
            assert kwargs["config"]["native_config"]["checkpoint_enabled"] is True
            return {"run_id": "run-123", "status": "queued", "source_pin": kwargs["source_pin"]}

        def transition_run(self, **_kwargs):
            raise AssertionError("queue should succeed")

    monkeypatch.setenv("DATAVEST_TRADING_AGENTS_SERVICE_SECRET", "must-not-reach-client")
    monkeypatch.setattr(route_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(route_module, "enqueue_run", lambda run_id: queued.append(run_id))

    response = client.post(
        "/api/trading-agents/runs",
        json={
            "market": "Crypto",
            "symbol": "BTC/USDT",
            "analysisDate": "2026-09-05",
            "nativeConfig": {"quick_think_llm": "deepseek-chat"},
        },
    )

    assert response.status_code == 202
    assert queued == ["run-123"]
    assert response.get_json()["data"] == {"run_id": "run-123", "status": "queued"}
    assert "DATAVEST_TRADING_AGENTS" not in response.get_data(as_text=True)
    assert "must-not-reach-client" not in response.get_data(as_text=True)


def test_cancel_queues_idempotent_control_for_owned_run(monkeypatch):
    client, route_module = _client(monkeypatch)
    transitions = []
    controls = []

    class Repository:
        def get_owned_run(self, **_kwargs):
            return {"run_id": "run-123", "status": "running"}

        def transition_run(self, **kwargs):
            transitions.append(kwargs)

    monkeypatch.setattr(route_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(route_module, "enqueue_trading_agents_control", lambda run_id, action: controls.append((run_id, action)))

    response = client.post("/api/trading-agents/runs/run-123/cancel")

    assert response.status_code == 202
    assert transitions == [{"run_id": "run-123", "status": "cancelled"}]
    assert controls == [("run-123", "cancel")]


def test_completed_run_cannot_be_cancelled(monkeypatch):
    client, route_module = _client(monkeypatch)
    transitions = []
    controls = []

    class Repository:
        def get_owned_run(self, **_kwargs):
            return {"run_id": "run-123", "status": "succeeded"}

        def transition_run(self, **kwargs):
            transitions.append(kwargs)

    monkeypatch.setattr(route_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(route_module, "enqueue_trading_agents_control", lambda run_id, action: controls.append((run_id, action)))

    response = client.post("/api/trading-agents/runs/run-123/cancel")

    assert response.status_code == 409
    assert transitions == []
    assert controls == []


def test_artifact_checksum_mismatch_is_not_served(monkeypatch):
    client, route_module = _client(monkeypatch)

    class Repository:
        def get_owned_run(self, **_kwargs):
            return {
                "run_id": "run-123",
                "user_id": 7,
                "artifacts": [{
                    "artifact_name": "complete_report.md",
                    "sha256": hashlib.sha256(b"expected").hexdigest(),
                }],
            }

    monkeypatch.setattr(route_module, "get_repository", lambda: Repository())
    monkeypatch.setattr(route_module, "fetch_artifact_from_service", lambda **_kwargs: (b"changed", "text/markdown"))

    response = client.get("/api/trading-agents/runs/run-123/artifacts/complete_report.md")

    assert response.status_code == 503
    assert response.get_json()["msg"] == "trading_agents_artifact_unavailable"
