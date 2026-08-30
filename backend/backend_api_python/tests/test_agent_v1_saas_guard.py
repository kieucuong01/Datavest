"""Tests for Agent Token issuance policy on SaaS and self-service routes."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.routes.agent_v1 import admin as admin_routes
from app.services import agent_token_service
from app.utils import agent_auth, auth as core_auth


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, False),
        ("", False),
        ("self", False),
        ("local", False),
        ("saas", True),
        ("SaaS", True),
        ("HOSTED", True),
        ("shared", True),
        ("multitenant", True),
        ("multi-tenant", True),
    ],
)
def test_is_saas_mode_recognizes_known_spellings(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("QUANTDINGER_DEPLOYMENT_MODE", raising=False)
    else:
        monkeypatch.setenv("QUANTDINGER_DEPLOYMENT_MODE", raw)
    assert agent_token_service.is_saas_mode() is expected
    assert admin_routes._is_saas_mode() is expected


@pytest.fixture
def admin_authed(monkeypatch):
    monkeypatch.setattr(
        core_auth,
        "verify_token",
        lambda _raw: {
            "sub": "tester",
            "user_id": 42,
            "role": "admin",
            "_verified_username": "tester",
            "_verified_user_role": "admin",
        },
    )
    yield {"user_id": 42}


@pytest.fixture
def user_authed(monkeypatch):
    monkeypatch.setattr(
        core_auth,
        "verify_token",
        lambda _raw: {
            "sub": "alice",
            "user_id": 7,
            "role": "user",
            "_verified_username": "alice",
            "_verified_user_role": "user",
        },
    )
    yield {"user_id": 7}


@pytest.fixture
def stub_db_for_issue(monkeypatch):
    class _StubCursor:
        def __init__(self):
            self._row = None
            self._last_sql = ""

        def execute(self, sql, _params=None):
            self._last_sql = (sql or "").upper()

        def fetchone(self):
            if "INSERT" in self._last_sql:
                return {"id": 1, "created_at": datetime(2026, 5, 2, 0, 0, 0)}
            if "SELECT" in self._last_sql and "TOKEN_HASH" in self._last_sql:
                return {"id": 1, "created_at": datetime(2026, 5, 2, 0, 0, 0)}
            return None

        def fetchall(self):
            if "FROM QD_AGENT_TOKENS" in self._last_sql:
                return [{
                    "id": 1,
                    "name": "cursor-mcp",
                    "token_prefix": "qd_agent_ab",
                    "scopes": "B,R",
                    "markets": ["*"],
                    "instruments": ["*"],
                    "paper_only": True,
                    "rate_limit_per_min": 60,
                    "status": "active",
                    "expires_at": None,
                    "last_used_at": None,
                    "created_at": datetime(2026, 5, 2, 0, 0, 0),
                }]
            if "FROM QD_AGENT_AUDIT" in self._last_sql:
                return []
            return []

        def close(self):
            pass

        @property
        def rowcount(self):
            return 0

    class _StubConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def cursor(self):
            return _StubCursor()

        def commit(self):
            pass

    monkeypatch.setattr(agent_token_service, "get_db_connection", lambda: _StubConn())


def _post_admin_issue(client, payload, *, base_url="http://localhost"):
    return client.post(
        "/api/agent/v1/admin/tokens",
        headers={
            "Authorization": "Bearer admin-jwt",
            "Content-Type": "application/json",
        },
        json=payload,
        base_url=base_url,
    )


def _post_me_issue(client, payload, *, base_url="http://localhost"):
    return client.post(
        "/api/agent/v1/me/tokens",
        headers={
            "Authorization": "Bearer user-jwt",
            "Content-Type": "application/json",
        },
        json=payload,
        base_url=base_url,
    )


@pytest.mark.parametrize("deployment_mode", [None, "saas", "hosted"])
def test_admin_tokens_reject_removed_T_scope(
    client, admin_authed, stub_db_for_issue, monkeypatch, deployment_mode
):
    if deployment_mode is None:
        monkeypatch.delenv("QUANTDINGER_DEPLOYMENT_MODE", raising=False)
    else:
        monkeypatch.setenv("QUANTDINGER_DEPLOYMENT_MODE", deployment_mode)

    resp = _post_admin_issue(client, {
        "name": "research-agent",
        "scopes": "R,T",
        "paper_only": True,
    })
    assert resp.status_code == 400
    assert "Unknown scope" in resp.get_json()["message"]


def test_me_tokens_rejects_C_scope(
    client, user_authed, stub_db_for_issue, monkeypatch
):
    monkeypatch.delenv("QUANTDINGER_DEPLOYMENT_MODE", raising=False)

    resp = _post_me_issue(client, {
        "name": "user-c-attempt",
        "scopes": "R,C",
        "paper_only": True,
    })
    assert resp.status_code == 400
    assert "Unknown scope" in resp.get_json()["message"]


def test_me_tokens_issue_and_policy(client, user_authed, stub_db_for_issue, monkeypatch):
    monkeypatch.setenv("QUANTDINGER_DEPLOYMENT_MODE", "saas")

    policy = client.get(
        "/api/agent/v1/me/tokens/policy",
        headers={"Authorization": "Bearer user-jwt"},
        base_url="http://localhost",
    )
    assert policy.status_code == 200
    pdata = policy.get_json()["data"]
    assert pdata["is_saas"] is True
    assert pdata["allowed_scopes"] == ["B", "N", "R", "W"]
    assert pdata["risk_disclosure"]["system"]

    resp = _post_me_issue(client, {
        "name": "cursor-mcp",
        "scopes": "R,B",
        "paper_only": True,
    })
    assert resp.status_code == 200
    assert resp.get_json()["data"]["token"].startswith(agent_auth.TOKEN_PREFIX)

    listed = client.get(
        "/api/agent/v1/me/tokens",
        headers={"Authorization": "Bearer user-jwt"},
        base_url="http://localhost",
    )
    assert listed.status_code == 200


def test_me_revoke_other_users_token_returns_404(client, user_authed, monkeypatch):
    class _StubCursor:
        def execute(self, _sql, _params=None):
            pass

        def close(self):
            pass

        @property
        def rowcount(self):
            return 0

    class _StubConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def cursor(self):
            return _StubCursor()

        def commit(self):
            pass

    monkeypatch.setattr(agent_token_service, "get_db_connection", lambda: _StubConn())

    resp = client.delete(
        "/api/agent/v1/me/tokens/999",
        headers={"Authorization": "Bearer user-jwt"},
        base_url="http://localhost",
    )
    assert resp.status_code == 404
