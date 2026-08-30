"""Focused contracts for the expanded Agent Gateway and safety middleware."""
from __future__ import annotations

import pytest

from app.routes.agent_v1 import research
from app.utils import agent_auth


def _token(scopes: str = "R,W,B,N") -> dict:
    return {
        "id": 501,
        "user_id": 7,
        "name": "full-surface-agent",
        "scopes": scopes,
        "markets": "*",
        "instruments": "*",
        "paper_only": True,
        "rate_limit_per_min": 100,
        "max_order_notional": 1000,
        "max_daily_notional": 5000,
        "status": "active",
        "expires_at": None,
    }


def _headers(*, key: str | None = None) -> dict:
    headers = {"Authorization": "Bearer qd_agent_FULLSURFACE12345"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


@pytest.fixture(autouse=True)
def _authorized(monkeypatch):
    agent_auth._schema_ready = True
    agent_auth._rate_state.clear()
    monkeypatch.setattr(agent_auth, "_lookup_token", lambda _raw: _token())
    monkeypatch.setattr(agent_auth, "_touch_token_last_used", lambda *_: None)
    monkeypatch.setattr(agent_auth, "_audit", lambda *args, **kwargs: None)
    yield
    agent_auth._rate_state.clear()


def test_rate_limit_headers_are_returned(client):
    response = client.get("/api/agent/v1/whoami", headers=_headers())
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "100"
    assert int(response.headers["X-RateLimit-Remaining"]) == 99
    assert int(response.headers["X-RateLimit-Reset"]) > 0


def test_mutating_scope_requires_idempotency_key(client):
    response = client.post(
        "/api/agent/v1/research/watchlist",
        headers=_headers(),
        json={"market": "USStock", "symbol": "AAPL"},
    )
    assert response.status_code == 400
    assert "Idempotency-Key" in response.get_json()["message"]


def test_completed_idempotent_response_is_replayed(client, monkeypatch):
    monkeypatch.setattr(
        agent_auth,
        "_reserve_idempotency",
        lambda *_: (
            "completed",
            {
                "response_body": {
                    "code": 0,
                    "message": "added",
                    "data": {"market": "USStock", "symbol": "AAPL"},
                },
                "response_status": 200,
            },
        ),
    )
    monkeypatch.setattr(
        research,
        "add_watchlist_item",
        lambda *_args, **_kwargs: pytest.fail("replayed request reached route logic"),
    )
    response = client.post(
        "/api/agent/v1/research/watchlist",
        headers=_headers(key="watchlist-aapl"),
        json={"market": "USStock", "symbol": "AAPL"},
    )
    assert response.status_code == 200
    assert response.headers["Idempotent-Replayed"] == "true"
    assert response.get_json()["data"]["symbol"] == "AAPL"


def test_reused_key_with_different_payload_is_rejected(client, monkeypatch):
    monkeypatch.setattr(
        agent_auth,
        "_reserve_idempotency",
        lambda *_: ("mismatch", {"request_hash": "different"}),
    )
    response = client.post(
        "/api/agent/v1/research/watchlist",
        headers=_headers(key="reused-key"),
        json={"market": "USStock", "symbol": "MSFT"},
    )
    assert response.status_code == 409


def test_factor_registry_is_exposed(client):
    response = client.get(
        "/api/agent/v1/research/factors?category=momentum",
        headers=_headers(),
    )
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert any(item["factor_id"] == "rsi" for item in items)
