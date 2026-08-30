"""Application startup contracts for database bootstrap failures."""

from __future__ import annotations

import pytest

import app as app_module
from app.runtime.roles import ProcessRole


def test_database_bootstrap_propagates_unexpected_admin_failure(monkeypatch):
    from app import runtime
    from app import utils
    from app.services import user_service

    class FailingUserService:
        def ensure_admin_exists(self) -> None:
            raise RuntimeError(
                "ensure_admin_exists failed: UniqueViolation "
                "(constraint=qd_users_email_key)"
            )

    monkeypatch.setattr(utils.db, "get_db_type", lambda: "postgresql")
    monkeypatch.setattr(utils.db, "init_database", lambda: None)
    monkeypatch.setattr(runtime.roles, "current_process_role", lambda: ProcessRole.API)
    monkeypatch.setattr(user_service, "get_user_service", lambda: FailingUserService())

    with pytest.raises(RuntimeError, match="qd_users_email_key"):
        app_module._bootstrap_database()


def test_testing_app_does_not_run_production_database_bootstrap(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_bootstrap_database",
        lambda: pytest.fail("testing app attempted production database bootstrap"),
    )

    application = app_module.create_app("testing", register_http_routes=False)

    assert application is not None
