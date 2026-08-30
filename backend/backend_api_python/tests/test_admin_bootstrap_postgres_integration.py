"""Non-destructive PostgreSQL verification for bootstrap-admin races."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import pytest
from dotenv import dotenv_values

from app.services.user_service import UserService


def _test_database_url() -> str:
    explicit = os.getenv("DATAVEST_TEST_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    password = str(values.get("POSTGRES_PASSWORD") or "")
    if not password:
        pytest.skip("No isolated PostgreSQL test credentials are configured")
    user = quote(str(values.get("POSTGRES_USER") or "quantdinger"), safe="")
    database = quote(str(values.get("POSTGRES_DB") or "quantdinger"), safe="")
    return f"postgresql://{user}:{quote(password, safe='')}@127.0.0.1:55432/{database}"


class _CursorAdapter:
    def __init__(self, cursor, barrier: threading.Barrier) -> None:
        self._cursor = cursor
        self._barrier = barrier

    def execute(self, query: str, params=None):
        if "INSERT INTO qd_users" in query:
            self._barrier.wait(timeout=10)
        return self._cursor.execute(query.replace("?", "%s"), params)

    def fetchone(self):
        return self._cursor.fetchone()

    def close(self) -> None:
        self._cursor.close()


class _ConnectionAdapter:
    def __init__(self, connection, barrier: threading.Barrier, cursor_factory) -> None:
        self._connection = connection
        self._barrier = barrier
        self._cursor_factory = cursor_factory

    def cursor(self) -> _CursorAdapter:
        return _CursorAdapter(
            self._connection.cursor(cursor_factory=self._cursor_factory),
            self._barrier,
        )

    def commit(self) -> None:
        self._connection.commit()


def test_postgres_bootstrap_races_only_ignore_the_username_conflict():
    psycopg2 = pytest.importorskip("psycopg2")
    extras = pytest.importorskip("psycopg2.extras")
    sql = pytest.importorskip("psycopg2.sql")
    database_url = _test_database_url()
    schema = f"task7_bootstrap_{uuid.uuid4().hex}"

    try:
        setup = psycopg2.connect(database_url, connect_timeout=3)
    except psycopg2.OperationalError as error:
        pytest.skip(f"PostgreSQL test database unavailable: {type(error).__name__}")

    setup.autocommit = True
    setup_cursor = setup.cursor()
    try:
        setup_cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        setup_cursor.execute(
            sql.SQL(
                """
                CREATE TABLE {}.qd_users (
                    id BIGSERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    nickname VARCHAR(50),
                    role VARCHAR(20),
                    status VARCHAR(20),
                    email_verified BOOLEAN,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            ).format(sql.Identifier(schema))
        )

        service = UserService()

        def race_insert(username: str, email: str, barrier: threading.Barrier):
            connection = psycopg2.connect(database_url, connect_timeout=3)
            try:
                cursor = connection.cursor()
                cursor.execute(
                    sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema))
                )
                cursor.close()
                adapter = _ConnectionAdapter(connection, barrier, extras.RealDictCursor)
                return service._insert_bootstrap_admin_if_database_empty(
                    adapter,
                    username=username,
                    password_hash="integration-password-hash",
                    email=email,
                )
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        username_barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            username_futures = [
                executor.submit(
                    race_insert,
                    "task7-same-admin",
                    "task7-same@example.invalid",
                    username_barrier,
                )
                for _ in range(2)
            ]
        username_results = [future.result() for future in username_futures]
        assert sum(result is not None for result in username_results) == 1
        setup_cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.qd_users").format(sql.Identifier(schema))
        )
        assert setup_cursor.fetchone()[0] == 1

        setup_cursor.execute(
            sql.SQL("TRUNCATE TABLE {}.qd_users RESTART IDENTITY").format(
                sql.Identifier(schema)
            )
        )
        email_barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            email_futures = [
                executor.submit(
                    race_insert,
                    username,
                    "task7-shared@example.invalid",
                    email_barrier,
                )
                for username in ("task7-admin-a", "task7-admin-b")
            ]
        email_outcomes = []
        for future in email_futures:
            try:
                email_outcomes.append(("ok", future.result()))
            except Exception as error:
                email_outcomes.append(("error", error))

        assert sum(kind == "ok" for kind, _value in email_outcomes) == 1
        errors = [value for kind, value in email_outcomes if kind == "error"]
        assert len(errors) == 1
        assert getattr(errors[0], "pgcode", None) == "23505"
        assert getattr(getattr(errors[0], "diag", None), "constraint_name", None) == (
            "qd_users_email_key"
        )
        setup_cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.qd_users").format(sql.Identifier(schema))
        )
        assert setup_cursor.fetchone()[0] == 1
    finally:
        try:
            setup_cursor.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema))
            )
        finally:
            setup_cursor.close()
            setup.close()
