"""Scheduler heartbeat runtime contracts."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module

import pytest


class _Cursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple | None]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self.calls.append((" ".join(sql.split()), params))

    def close(self) -> None:
        self.closed = True


class _Connection:
    def __init__(self) -> None:
        self.cursor_instance = _Cursor()
        self.commits = 0

    def cursor(self) -> _Cursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1


def _heartbeat_module():
    try:
        return import_module("app.runtime.worker_heartbeat")
    except ModuleNotFoundError:
        pytest.fail("scheduler heartbeat service is missing")


def test_scheduler_heartbeat_upserts_stable_worker_and_can_stop(monkeypatch):
    heartbeat_module = _heartbeat_module()
    connection = _Connection()

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(heartbeat_module, "get_db_connection", fake_connection)
    monkeypatch.setattr(heartbeat_module.socket, "gethostname", lambda: "scheduler-host")

    heartbeat = heartbeat_module.WorkerHeartbeat("scheduler")
    heartbeat.record_running()
    heartbeat.mark_stopped()

    assert heartbeat.worker_id == "scheduler:scheduler-host"
    assert connection.commits == 2
    assert connection.cursor_instance.closed is True
    running_sql, running_params = connection.cursor_instance.calls[0]
    assert "ON CONFLICT (worker_id) DO UPDATE" in running_sql
    assert "status = 'running'" in running_sql
    assert running_params == ("scheduler:scheduler-host", "scheduler", "{}")
    stopped_sql, stopped_params = connection.cursor_instance.calls[1]
    assert "SET status = 'stopped'" in stopped_sql
    assert stopped_params == ("scheduler:scheduler-host",)


def test_scheduler_loop_records_immediately_refreshes_within_health_window_and_stops():
    from app.commands.scheduler import run_scheduler_loop

    events: list[object] = []

    class Heartbeat:
        def record_running(self) -> None:
            events.append("running")

        def mark_stopped(self) -> None:
            events.append("stopped")

    class Event:
        waits = 0

        def wait(self, timeout: float) -> bool:
            events.append(("wait", timeout))
            self.waits += 1
            return self.waits == 2

    class Shutdown:
        event = Event()

    run_scheduler_loop(
        shutdown=Shutdown(),
        heartbeat=Heartbeat(),
        start_services=lambda: events.append("services"),
    )

    assert events == [
        "running",
        "services",
        ("wait", 30),
        "running",
        ("wait", 30),
        "stopped",
    ]
