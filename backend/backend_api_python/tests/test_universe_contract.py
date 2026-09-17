from datetime import date

import pytest

from app.services.universe import (
    UniverseError,
    UniverseService,
    member_content_hash,
    normalize_members,
    normalize_universe_code,
    parse_as_of,
)


def test_manual_universe_members_are_canonical_and_deduplicated():
    members = normalize_members(
        [
            {"market": "USStock", "symbol": " msft ", "name": "Microsoft"},
            {"market": "USStock", "symbol": "AAPL", "name": "Apple"},
            {"market": "USStock", "symbol": "MSFT", "name": "Microsoft Corp."},
        ]
    )

    assert [item["symbol"] for item in members] == ["AAPL", "MSFT"]
    assert members[1]["name"] == "Microsoft Corp."
    assert all(item["market_type"] == "spot" for item in members)


def test_crypto_member_uses_canonical_market_context():
    member = normalize_members(
        [{"symbol": "btc/usdt:usdt", "exchange_id": "okex", "market_type": "perp"}],
        default_market="Crypto",
    )[0]

    assert member["symbol"] == "BTC/USDT"
    assert member["exchange_id"] == "okx"
    assert member["market_type"] == "swap"


def test_member_hash_is_stable_across_input_order_and_display_name_changes():
    left = normalize_members([
        {"market": "USStock", "symbol": "AAPL", "name": "Apple"},
        {"market": "USStock", "symbol": "MSFT", "name": "Microsoft"},
    ])
    right = normalize_members([
        {"market": "USStock", "symbol": "MSFT", "name": "MSFT"},
        {"market": "USStock", "symbol": "AAPL", "name": "AAPL"},
    ])

    assert member_content_hash(left) == member_content_hash(right)


def test_parse_as_of_is_strict_iso_date():
    assert parse_as_of("2026-07-11") == date(2026, 7, 11)
    with pytest.raises(UniverseError) as caught:
        parse_as_of("07/11/2026")
    assert caught.value.code == "universe.invalidAsOf"


def test_invalid_market_and_empty_symbol_are_rejected():
    with pytest.raises(UniverseError) as invalid_market:
        normalize_members([{"market": "Unknown", "symbol": "AAPL"}])
    assert invalid_market.value.code == "universe.invalidMarket"

    with pytest.raises(UniverseError) as invalid_symbol:
        normalize_members([{"market": "USStock", "symbol": ""}])
    assert invalid_symbol.value.code == "universe.invalidSymbol"


def test_user_universe_code_has_safe_fallback():
    assert normalize_universe_code("Quality + Momentum") == "quality-momentum"
    assert normalize_universe_code("沪深轮动") == "manual"


def test_symbol_master_historical_members_use_listing_interval_not_current_active(monkeypatch):
    from app.services import universe as universe_module

    executions = []
    rows = [{
        "market": "VNStock", "symbol": "OLD", "name": "Old Company",
        "exchange_id": "HOSE", "market_type": "spot", "instrument_id": "",
        "settle_currency": "VND",
    }]

    class Cursor:
        def execute(self, query, params):
            executions.append((" ".join(query.split()), params))

        def fetchall(self):
            return rows

        def close(self):
            return None

    class Database:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(universe_module, "get_db_connection", lambda: Database())

    members = UniverseService._symbol_master_members(
        "VNStock:all:equity", as_of=date(2019, 6, 30)
    )

    assert [item["symbol"] for item in members] == ["OLD"]
    sql, params = executions[0]
    assert "listed_date IS NULL OR listed_date <= ?" in sql
    assert "delisted_date IS NULL OR delisted_date > ?" in sql
    assert "is_active = 1" not in sql
    assert params == ("VNStock", "equity", date(2019, 6, 30), date(2019, 6, 30))


def test_symbol_master_range_candidates_include_any_overlapping_listing(monkeypatch):
    from app.services import universe as universe_module

    executions = []

    class Cursor:
        def execute(self, query, params):
            executions.append((" ".join(query.split()), params))

        def fetchall(self):
            return []

        def close(self):
            return None

    class Database:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(universe_module, "get_db_connection", lambda: Database())

    UniverseService._symbol_master_candidates(
        "VNStock:all:equity", start=date(2018, 1, 1), end=date(2020, 12, 31)
    )

    sql, params = executions[0]
    assert "listed_date IS NULL OR listed_date <= ?" in sql
    assert "delisted_date IS NULL OR delisted_date > ?" in sql
    assert params == ("VNStock", "equity", date(2020, 12, 31), date(2018, 1, 1))
