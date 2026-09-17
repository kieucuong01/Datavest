"""Initial market catalog synchronization tests."""

from __future__ import annotations


def test_initial_sync_starts_when_catalog_is_not_initialized(monkeypatch):
    from app.services import market_catalog_sync

    monkeypatch.setenv("MARKET_CATALOG_AUTO_SYNC", "true")
    monkeypatch.delenv("PYTHON_API_DEBUG", raising=False)
    monkeypatch.setattr(market_catalog_sync, "_market_catalog_is_initialized", lambda: False)
    monkeypatch.setattr(
        market_catalog_sync,
        "start_market_catalog_sync",
        lambda trigger: {"started": True, "run_id": 41, "trigger": trigger},
    )

    result = market_catalog_sync.start_market_catalog_sync_on_boot()

    assert result == {"started": True, "run_id": 41, "trigger": "startup"}


def test_initial_sync_skips_an_initialized_catalog(monkeypatch):
    from app.services import market_catalog_sync

    monkeypatch.setenv("MARKET_CATALOG_AUTO_SYNC", "true")
    monkeypatch.delenv("PYTHON_API_DEBUG", raising=False)
    monkeypatch.setattr(market_catalog_sync, "_market_catalog_is_initialized", lambda: True)
    monkeypatch.setattr(
        market_catalog_sync,
        "start_market_catalog_sync",
        lambda trigger: (_ for _ in ()).throw(AssertionError(f"unexpected sync: {trigger}")),
    )

    result = market_catalog_sync.start_market_catalog_sync_on_boot()

    assert result == {"started": False, "reason": "already_initialized"}


def test_initial_sync_respects_disabled_setting(monkeypatch):
    from app.services import market_catalog_sync

    monkeypatch.setenv("MARKET_CATALOG_AUTO_SYNC", "false")
    monkeypatch.setattr(
        market_catalog_sync,
        "_market_catalog_is_initialized",
        lambda: (_ for _ in ()).throw(AssertionError("database should not be queried")),
    )

    result = market_catalog_sync.start_market_catalog_sync_on_boot()

    assert result == {"started": False, "reason": "disabled"}


def test_catalog_worker_syncs_hose_as_a_safe_full_snapshot(monkeypatch):
    from app.services import market_catalog_sync
    from app.services.symbol_master_sync import SymbolMasterRow

    hose_rows = [
        SymbolMasterRow("VNStock", f"A{i:03}", f"Company {i}", "HOSE", "VND", asset_class="equity")
        for i in range(100)
    ]
    calls = []
    finished = []
    monkeypatch.setattr(
        market_catalog_sync,
        "fetch_crypto_symbols_with_diagnostics",
        lambda: ([], [{"exchange": "binance", "market_type": "spot", "ok": True, "rows": 0}]),
    )
    monkeypatch.setattr(market_catalog_sync, "fetch_vn_stock_symbols", lambda: hose_rows)
    monkeypatch.setattr(
        market_catalog_sync,
        "upsert_symbol_master",
        lambda rows, **kwargs: calls.append((rows, kwargs)) or len(rows),
    )
    monkeypatch.setattr(
        market_catalog_sync,
        "_finish_run",
        lambda run_id, status, result: finished.append((run_id, status, result)),
    )

    market_catalog_sync._run_sync(7)

    assert calls == [(hose_rows, {"full_snapshot_markets": {"VNStock"}})]
    assert finished[0][0:2] == (7, "success")
    assert finished[0][2]["hose"] == {"ok": True, "rows": 100, "upserted": 100}
