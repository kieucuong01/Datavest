"""HOSE search must use the active provider catalog, not curated ticker guesses."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3

import pytest

from app.data import market_symbols_seed as symbols
from app.services import symbol_master_sync
from app.services.market import symbol_search


class _Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=()):
        self.cursor.execute(query, params)

    def fetchall(self):
        return [dict(row) for row in self.cursor.fetchall()]

    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def close(self):
        self.cursor.close()


class _Database:
    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return _Cursor(self.connection.cursor())

    def commit(self):
        self.connection.commit()


@pytest.fixture
def catalog(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE qd_market_symbols (
            market TEXT, symbol TEXT, name TEXT, exchange TEXT, currency TEXT,
            market_type TEXT DEFAULT 'spot', instrument_id TEXT DEFAULT '',
            settle_currency TEXT DEFAULT '', asset_class TEXT, sector TEXT,
            listed_date TEXT, delisted_date TEXT, trading_status TEXT,
            source TEXT, source_updated_at TEXT, is_active INTEGER,
            is_hot INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
            UNIQUE(market, symbol, exchange, market_type, instrument_id)
        );
        CREATE TABLE qd_market_symbol_aliases (
            market TEXT, symbol TEXT, alias TEXT, is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0, UNIQUE(market, symbol, alias)
        );
        """
    )

    @contextmanager
    def database():
        yield _Database(connection)

    monkeypatch.setattr(symbols, "_get_db_connection", database)
    monkeypatch.setattr(symbol_master_sync, "get_db_connection", database)
    yield connection
    connection.close()


def _stock(db, symbol, name, *, exchange="HOSE", status="ACTIVE", active=1,
           source="vndirect", updated="2026-09-20T00:00:00Z", asset_class="equity"):
    db.execute(
        """INSERT INTO qd_market_symbols
           (market, symbol, name, exchange, currency, asset_class, trading_status,
            source, source_updated_at, is_active)
           VALUES ('VNStock', ?, ?, ?, 'VND', ?, ?, ?, ?, ?)""",
        (symbol, name, exchange, asset_class, status, source, updated, active),
    )


def test_vietnamese_search_normalization_is_accent_insensitive():
    assert symbols.normalize_vn_search("  Hòa   Phát ") == "hoa phat"
    assert symbols.normalize_vn_search("ĐẦU TƯ") == "dau tu"


def test_hose_search_matches_active_ticker_company_name_and_alias(catalog):
    _stock(catalog, "HPG", "Công ty Cổ phần Tập đoàn Hòa Phát")
    catalog.execute(
        "INSERT INTO qd_market_symbol_aliases (market, symbol, alias) VALUES ('VNStock', 'HPG', 'Hoa Phat')"
    )
    catalog.commit()

    for query in ("HPG", "Hòa Phát", "Hoa Phat"):
        rows = symbols.search_symbols("VNStock", query, exchange="HOSE")
        assert [row["symbol"] for row in rows] == ["HPG"]
        assert rows[0]["exchange"] == "HOSE"
        assert rows[0]["currency"] == "VND"


def test_hose_search_fails_closed_for_delisted_wrong_exchange_and_unverified_source(catalog):
    _stock(catalog, "OLD", "Old Company", status="DELISTED", active=0)
    _stock(catalog, "HNX", "HNX Company", exchange="HNX")
    _stock(catalog, "STATIC", "Static Company", source="seed")
    _stock(catalog, "STALE", "Stale Company", updated=None)
    catalog.execute(
        "INSERT INTO qd_market_symbol_aliases (market, symbol, alias) VALUES ('VNStock', 'OLD', 'DELISTED_ALIAS')"
    )
    catalog.commit()

    for query in ("DELISTED_ALIAS", "HNX", "STATIC", "STALE"):
        assert symbols.search_symbols("VNStock", query, exchange="HOSE") == []


def test_hose_sync_generates_accentless_alias_without_overwriting_curated_alias(catalog):
    catalog.execute(
        "INSERT INTO qd_market_symbol_aliases (market, symbol, alias) VALUES ('VNStock', 'HPG', 'Tập đoàn thép')"
    )
    row = symbol_master_sync.SymbolMasterRow(
        "VNStock", "HPG", "Tập đoàn Hòa Phát", "HOSE", "VND",
        asset_class="equity", source="vndirect",
        source_updated_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
    )

    assert symbol_master_sync.upsert_symbol_master([row]) == 1
    aliases = {
        item[0] for item in catalog.execute(
            "SELECT alias FROM qd_market_symbol_aliases WHERE symbol='HPG'"
        ).fetchall()
    }
    assert {"tap doan hoa phat", "Tập đoàn thép"} <= aliases


def test_market_search_returns_hose_exchange_and_currency(catalog):
    _stock(catalog, "HPG", "Tập đoàn Hòa Phát")
    catalog.execute(
        "INSERT INTO qd_market_symbol_aliases (market, symbol, alias) VALUES ('VNStock', 'HPG', 'tap doan hoa phat')"
    )
    catalog.commit()

    rows = symbol_search.search_market_symbols("VNStock", "hoa phat", exchange="HOSE")
    assert [row["symbol"] for row in rows] == ["HPG"]
    assert rows[0]["exchange"] == "HOSE"
    assert rows[0]["currency"] == "VND"
    assert symbol_search.search_market_symbols("VNStock", "HPG", exchange="HNX") == []
