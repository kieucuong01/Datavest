from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import pytest

from app.data.market_symbols_seed import get_active_hose_symbol, validate_hose_ai_target
from app.services import symbol_master_sync
from app.services.symbol_master_sync import SymbolMasterRow, upsert_symbol_master


class FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.executed = []

    def execute(self, query, params=()):
        self.executed.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.row

    def close(self):
        pass


class FakeConnection:
    def __init__(self, row=None):
        self.cursor_value = FakeCursor(row)
        self.committed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True


def connection_factory(connection):
    @contextmanager
    def factory():
        yield connection

    return factory


def test_hose_full_snapshot_deactivates_missing_symbols_only_after_safety_threshold(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(symbol_master_sync, "get_db_connection", connection_factory(connection))
    rows = [
        SymbolMasterRow(
            "VNStock", f"A{i:03}", f"Company {i}", "HOSE", "VND",
            asset_class="equity", sector="Industrials", listed_date=date(2020, 1, 1),
            trading_status="ACTIVE", source="vndirect",
        )
        for i in range(100)
    ]

    written = upsert_symbol_master(rows, full_snapshot_markets={"VNStock"})

    assert written == 100
    queries = connection.cursor_value.executed
    assert "UPDATE qd_market_symbols SET is_active = 0" in queries[0][0]
    assert queries[0][1] == ("VNStock", "HOSE")
    assert any("sector" in query and "listed_date" in query and "trading_status" in query for query, _ in queries[1:])
    assert connection.committed is True


def test_small_hose_snapshot_never_deactivates_last_known_good_catalog(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(symbol_master_sync, "get_db_connection", connection_factory(connection))
    row = SymbolMasterRow("VNStock", "FPT", "FPT", "HOSE", "VND", source="vndirect")

    upsert_symbol_master([row], full_snapshot_markets={"VNStock"})

    assert not any("SET is_active = 0" in query for query, _ in connection.cursor_value.executed)


def test_provider_snapshot_below_threshold_is_rejected_before_database_write(monkeypatch):
    from app.data_sources import vn_market_providers

    class SmallSnapshotProvider:
        def fetch_universe(self):
            return [
                vn_market_providers.VietnamSecurity(
                    symbol="FPT", name="FPT", exchange="HOSE", asset_class="equity"
                )
            ]

    monkeypatch.setattr(vn_market_providers, "VndirectProvider", SmallSnapshotProvider)
    monkeypatch.setenv("HOSE_SNAPSHOT_MIN_ROWS", "100")

    with pytest.raises(RuntimeError, match="below safety threshold"):
        symbol_master_sync.fetch_vn_stock_symbols()


def test_active_hose_lookup_rejects_inactive_or_delisted_security(monkeypatch):
    from app.data import market_symbols_seed

    active_connection = FakeConnection({
        "market": "VNStock", "symbol": "FPT", "name": "FPT", "exchange": "HOSE",
        "asset_class": "equity", "trading_status": "ACTIVE", "delisted_date": None,
    })
    monkeypatch.setattr(market_symbols_seed, "_get_db_connection", connection_factory(active_connection))
    assert get_active_hose_symbol("fpt")["symbol"] == "FPT"
    lookup_sql = active_connection.cursor_value.executed[0][0]
    assert "source = 'vndirect'" in lookup_sql
    assert "source_updated_at IS NOT NULL" in lookup_sql

    inactive_connection = FakeConnection(None)
    monkeypatch.setattr(market_symbols_seed, "_get_db_connection", connection_factory(inactive_connection))
    assert get_active_hose_symbol("OLD") is None


def test_ai_target_validation_normalizes_active_hose_symbol_and_rejects_unknown(monkeypatch):
    from app.data import market_symbols_seed

    monkeypatch.setattr(
        market_symbols_seed,
        "get_active_hose_symbol",
        lambda symbol: {"symbol": symbol} if symbol == "FPT" else None,
    )

    assert validate_hose_ai_target("VNStock", "fpt.vn") == "FPT"
    assert validate_hose_ai_target("Crypto", "BTC/USDT") == "BTC/USDT"
    with pytest.raises(ValueError, match="unsupported_or_inactive_vn_symbol"):
        validate_hose_ai_target("VNStock", "NOTREAL")


def test_fast_analysis_service_rejects_invalid_hose_symbol_before_collecting_data(monkeypatch):
    from app.services import fast_analysis

    monkeypatch.setattr(
        fast_analysis,
        "validate_hose_ai_target",
        lambda _market, _symbol: (_ for _ in ()).throw(
            ValueError("unsupported_or_inactive_vn_symbol")
        ),
    )

    service = fast_analysis.FastAnalysisService.__new__(fast_analysis.FastAnalysisService)
    with pytest.raises(ValueError, match="unsupported_or_inactive_vn_symbol"):
        service.analyze("VNStock", "OLD")


def test_trading_agents_repository_rejects_invalid_hose_symbol_before_run_write(monkeypatch):
    from app.services import trading_agents_repository

    monkeypatch.setattr(
        trading_agents_repository,
        "validate_hose_ai_target",
        lambda _market, _symbol: (_ for _ in ()).throw(
            ValueError("unsupported_or_inactive_vn_symbol")
        ),
    )
    monkeypatch.setattr(
        trading_agents_repository,
        "get_db_connection",
        lambda: (_ for _ in ()).throw(AssertionError("invalid symbol reached database")),
    )

    with pytest.raises(ValueError, match="unsupported_or_inactive_vn_symbol"):
        trading_agents_repository.TradingAgentsRepository().create_run(
            user_id=7,
            request={"market": "VNStock", "symbol": "OLD", "analysis_date": "2026-09-16"},
            config={},
            source_pin="test/source@123",
        )
