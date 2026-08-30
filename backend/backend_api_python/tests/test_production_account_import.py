"""Contracts for the one-time DataVest production account importer."""

import pytest

from app.tools.import_production_account import (
    AccountImportError,
    build_import_plan,
    infer_local_market,
    normalize_source_symbol,
    safe_username,
)


def _payload():
    return {
        "schemaVersion": 1,
        "source": "datavest.vn",
        "user": {
            "id": "prod-user-1",
            "email": "person@example.com",
            "name": "Test Investor",
            "emailVerified": True,
        },
        "portfolio": {
            "portfolioId": "portfolio-1",
            "portfolioName": "Main Portfolio",
            "holdings": [
                {
                    "assetId": "btc-1",
                    "ticker": "BTC",
                    "name": "Bitcoin",
                    "qty": 0.1,
                    "cost": 65000,
                    "currency": "USD",
                    "category": "Crypto",
                },
                {
                    "assetId": "hpg-1",
                    "ticker": "HPG",
                    "name": "Hoa Phat Group",
                    "qty": 100,
                    "cost": 0.8,
                    "currency": "VND",
                    "category": "Stocks",
                },
            ],
            "transactions": [{"id": "tx-1", "type": "BUY"}],
            "performance": [{"label": "2026-08-01", "Portfolio": 100}],
        },
        "watchlist": [],
        "assets": [{"id": "btc-1", "symbol": "BTC", "assetClass": "crypto", "currency": "USDT"}],
        "briefing": {"id": "briefing-1", "assetOpinions": []},
        "briefingDates": {"today": "2026-08-26", "dates": ["2026-08-26"]},
        "preferences": {"preference": {"markets": ["crypto"], "locale": "vi"}},
        "regimes": {"regimes": [{"id": "regime-1"}]},
        "calendar": {"events": [{"id": "event-1"}]},
        "cryptoPulse": {"generatedAt": "2026-08-26T00:00:00Z"},
        "dataHealth": {"sources": [{"id": "source-1"}]},
        "researchRuns": [{"id": "research-1"}],
        "quantRuns": [],
        "customStrategies": [],
        "notifications": {"items": []},
    }


def test_market_mapping_keeps_vietnamese_symbols_explicit():
    assert infer_local_market({"assetClass": "crypto", "currency": "USDT"}) == "Crypto"
    assert infer_local_market({"assetClass": "equity", "currency": "VND"}) == "VNStock"
    assert infer_local_market({"assetClass": "commodity", "currency": "USD", "symbol": "XAUUSD"}) == "Forex"
    assert normalize_source_symbol("BTC", "Crypto") == "BTC/USDT"


def test_safe_username_is_stable_and_bounded():
    assert safe_username("person@example.com", "prod-user-1") == "person"
    assert safe_username("bad+alias@example.com", "prod-user-1") == "bad_alias"
    assert 3 <= len(safe_username("@", "1234567890")) <= 50


def test_import_plan_preserves_all_related_records_and_positions():
    plan = build_import_plan(_payload())

    assert plan.source_user_id == "prod-user-1"
    assert plan.email == "person@example.com"
    assert len(plan.position_rows) == 2
    assert plan.position_rows[0]["market"] == "Crypto"
    assert plan.position_rows[1]["market"] == "VNStock"
    assert plan.record_counts["portfolio_transaction"] == 1
    assert plan.record_counts["portfolio_performance"] == 1
    assert plan.record_counts["research_run"] == 1
    assert "password" not in plan.serialized_payload.lower()


@pytest.mark.parametrize(
    "bad_key",
    ["token", "password", "passwordHash", "sessionToken", "accessToken", "refreshToken"],
)
def test_import_rejects_secret_bearing_exports(bad_key):
    payload = _payload()
    payload["user"][bad_key] = "should-not-be-imported"

    with pytest.raises(AccountImportError, match="secret_field"):
        build_import_plan(payload)


def test_import_rejects_missing_identity():
    payload = _payload()
    del payload["user"]["email"]

    with pytest.raises(AccountImportError, match="missing_user_email"):
        build_import_plan(payload)
