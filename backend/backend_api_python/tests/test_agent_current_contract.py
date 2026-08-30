from __future__ import annotations

import pytest
from flask import g

from app.routes.agent_v1.backtests import _validate_request
from app.utils import agent_auth


STATIC_CODE = """
def initialize(context):
    context.set_universe(["USStock:AAPL"])
    context.set_benchmark("USStock:SPY")
    context.subscribe(frequency="1d")

def handle_data(context, data):
    pass
"""


DYNAMIC_CODE = """
def initialize(context):
    context.set_universe(pool="sp500")
    context.subscribe(frequency="1d")
    run_weekly(rebalance)

def rebalance(context, data):
    pass
"""


def _payload(code: str) -> dict:
    return {
        "code": code,
        "startDate": "2025-01-01",
        "endDate": "2025-12-31",
        "params": {},
    }


def test_backtest_rejects_missing_dates(app):
    with app.test_request_context("/"):
        g.agent_token = {"markets": "*", "instruments": "*"}
        _, err = _validate_request({"code": STATIC_CODE})
        assert err[1] == 400
        assert err[0].get_json()["message"].startswith("startDate and endDate")


def test_backtest_checks_benchmark_against_instrument_allowlist(app):
    with app.test_request_context("/"):
        g.agent_token = {"markets": "USStock", "instruments": "AAPL"}
        _, err = _validate_request(_payload(STATIC_CODE))
        assert err[1] == 403
        assert err[0].get_json()["message"] == "Instrument not allowed: SPY"


def test_backtest_rejects_dynamic_universe_for_restricted_token(app):
    with app.test_request_context("/"):
        g.agent_token = {"markets": "*", "instruments": "AAPL"}
        _, err = _validate_request(_payload(DYNAMIC_CODE))
        assert err[1] == 403
        assert "Dynamic universes" in err[0].get_json()["message"]


@pytest.fixture(autouse=True)
def _reset_agent_auth(monkeypatch):
    agent_auth._rate_state.clear()
    monkeypatch.setattr(agent_auth, "_reserve_idempotency", lambda *_: ("reserved", None))
    monkeypatch.setattr(agent_auth, "_complete_idempotency", lambda *_: None)
    yield
    agent_auth._rate_state.clear()
