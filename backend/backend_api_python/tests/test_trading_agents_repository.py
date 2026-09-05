"""Persistence contracts for durable TradingAgents research runs."""

from __future__ import annotations

import sys
import types
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _enable_lightweight_app_imports() -> None:
    """Avoid booting the full Flask factory for focused repository unit tests."""
    if "app" not in sys.modules:
        package = types.ModuleType("app")
        package.__path__ = [str(BACKEND_ROOT / "app")]
        sys.modules["app"] = package
    if "app.utils" not in sys.modules:
        utils_package = types.ModuleType("app.utils")
        utils_package.__path__ = [str(BACKEND_ROOT / "app" / "utils")]
        sys.modules["app.utils"] = utils_package


def test_migration_defines_owner_scoped_immutable_run_tables():
    migration = (
        BACKEND_ROOT / "migrations" / "20260905_trading_agents.sql"
    ).read_text(encoding="utf-8")

    for table in (
        "trading_agents_runs",
        "trading_agents_events",
        "trading_agents_artifacts",
        "trading_agents_proposals",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration

    assert "REFERENCES qd_users(id)" in migration
    assert "UNIQUE (run_id, sequence)" in migration
    assert "trading_agents_runs_immutable_fields" in migration
    assert "NEW.request_json IS DISTINCT FROM OLD.request_json" in migration
    assert "NEW.config_checksum IS DISTINCT FROM OLD.config_checksum" in migration
    assert "NEW.source_pin IS DISTINCT FROM OLD.source_pin" in migration


def test_database_bootstrap_resolves_trading_agents_migration():
    _enable_lightweight_app_imports()
    from app.utils import db

    assert db._resolve_trading_agents_sql_path().name == "20260905_trading_agents.sql"


def test_repository_persists_ordered_event_without_callback_user_id(monkeypatch):
    _enable_lightweight_app_imports()
    from app.services import trading_agents_repository as repository_module
    from app.services.trading_agents_repository import TradingAgentsRepository

    class Cursor:
        def __init__(self):
            self.calls = []
            self.lastrowid = None

        def execute(self, query, params=()):
            self.calls.append((query, params))

        def fetchone(self):
            return {"run_id": "run-123", "user_id": 7, "status": "queued"}

        def fetchall(self):
            return []

        def close(self):
            return None

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()
            self.commits = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.commits += 1

    connection = Connection()
    monkeypatch.setattr(repository_module, "get_db_connection", lambda: connection)

    TradingAgentsRepository().append_event(
        run_id="run-123",
        sequence=1,
        event_type="tool",
        payload={"status": "configured"},
    )

    query, params = connection.cursor_instance.calls[0]
    assert "INSERT INTO trading_agents_events" in query
    assert "SELECT ?, user_id" in query
    assert params[:3] == ("run-123", 1, "tool")
    assert connection.commits == 1


def test_failed_run_transition_does_not_store_raw_traceback(monkeypatch):
    _enable_lightweight_app_imports()
    from app.services import trading_agents_repository as repository_module
    from app.services.trading_agents_repository import TradingAgentsRepository

    class Cursor:
        def __init__(self):
            self.calls = []

        def execute(self, query, params=()):
            self.calls.append((query, params))

        def close(self):
            return None

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            return None

    connection = Connection()
    monkeypatch.setattr(repository_module, "get_db_connection", lambda: connection)

    TradingAgentsRepository().transition_run(
        run_id="run-123",
        status="failed",
        failure_message="Traceback (most recent call last): secret=do-not-store",
    )

    _query, params = connection.cursor_instance.calls[0]
    assert params[4] == "TradingAgents service failed; inspect private service logs."
