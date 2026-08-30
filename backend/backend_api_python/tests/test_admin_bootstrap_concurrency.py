"""Concurrency contracts for bootstrap administrator creation."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

import app.services.user_service as user_service_module
from app.services.user_service import UserService


class _Cursor:
    def __init__(self, inserted_row=None, execute_error: Exception | None = None) -> None:
        self.inserted_row = inserted_row
        self.execute_error = execute_error
        self.calls: list[tuple[str, tuple | None]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self.calls.append((" ".join(sql.split()), params))
        if self.execute_error is not None:
            raise self.execute_error

    def fetchone(self):
        return self.inserted_row

    def close(self) -> None:
        self.closed = True


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self.cursor_instance = cursor
        self.commits = 0

    def cursor(self) -> _Cursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1


def _install_database(monkeypatch, cursor: _Cursor) -> _Connection:
    connection = _Connection(cursor)

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(user_service_module, "get_db_connection", fake_connection)
    return connection


def _configure_service(monkeypatch, service: UserService) -> list[str]:
    monkeypatch.setenv("ADMIN_USER", "releaseadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "safe-admin-password")
    monkeypatch.setenv("ADMIN_EMAIL", "release@example.com")
    monkeypatch.setattr(service, "ensure_password_changed_column", lambda: None)
    monkeypatch.setattr(service, "hash_password", lambda _password: "safe-password-hash")
    monkeypatch.setattr(service, "_seed_new_user_defaults", lambda *_args: None, raising=False)
    sync_calls: list[str] = []
    monkeypatch.setattr(
        service,
        "sync_bootstrap_admin_credentials_from_env",
        lambda: sync_calls.append("credentials"),
    )
    monkeypatch.setattr(
        service,
        "sync_admin_email_from_config",
        lambda **_kwargs: sync_calls.append("email"),
    )
    return sync_calls


def test_admin_bootstrap_uses_atomic_username_conflict_and_syncs_after_insert(monkeypatch):
    service = UserService()
    sync_calls = _configure_service(monkeypatch, service)
    cursor = _Cursor(inserted_row={"id": 17})
    connection = _install_database(monkeypatch, cursor)

    service.ensure_admin_exists()

    insert_sql, params = cursor.calls[0]
    assert "INSERT INTO qd_users" in insert_sql
    assert "WHERE NOT EXISTS (SELECT 1 FROM qd_users)" in insert_sql
    assert "ON CONFLICT (username) DO NOTHING" in insert_sql
    assert "RETURNING id" in insert_sql
    assert params == (
        "releaseadmin",
        "safe-password-hash",
        None,
        "Administrator",
        "admin",
        "active",
        False,
    )
    email_sql, email_params = cursor.calls[1]
    assert "SET email = ?" in email_sql
    assert email_params == ("release@example.com", 17)
    assert connection.commits == 1
    assert sync_calls == ["credentials", "email"]


def test_admin_bootstrap_username_race_is_idempotent_and_still_syncs(monkeypatch):
    service = UserService()
    sync_calls = _configure_service(monkeypatch, service)
    cursor = _Cursor(inserted_row=None)
    connection = _install_database(monkeypatch, cursor)

    service.ensure_admin_exists()

    assert connection.commits == 1
    assert len(cursor.calls) == 1
    assert sync_calls == ["credentials", "email"]


def test_admin_bootstrap_does_not_treat_other_unique_errors_as_success(monkeypatch):
    service = UserService()
    sync_calls = _configure_service(monkeypatch, service)
    secret = "safe-admin-password"
    error_messages: list[str] = []
    cursor = _Cursor(execute_error=RuntimeError("duplicate key on qd_users_email_key"))
    _install_database(monkeypatch, cursor)
    monkeypatch.setattr(
        user_service_module.logger,
        "error",
        lambda message, *args, **_kwargs: error_messages.append(message % args if args else message),
    )

    with pytest.raises(RuntimeError, match="qd_users_email_key"):
        service.ensure_admin_exists()

    assert error_messages
    assert "qd_users_email_key" in error_messages[0]
    assert secret not in error_messages[0]
    assert sync_calls == []
