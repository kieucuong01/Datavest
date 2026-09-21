from __future__ import annotations

from app.services.vietnam_market_health import classify_provider_health, finalize_eod_batch


def test_vndirect_success_and_yahoo_rate_limit_is_degraded_not_unavailable():
    health = classify_provider_health([
        {"provider": "vndirect", "status": "ok", "bars": 2},
        {"provider": "yahoo-vn", "status": "unavailable", "error": "http_429"},
    ])

    assert health["status"] == "degraded"
    assert health["providers"][0] == {"provider": "vndirect", "status": "ok", "bars": 2}
    assert health["providers"][1]["error"] == "http_429"


def test_all_provider_failures_are_explicitly_unavailable():
    health = classify_provider_health([
        {"provider": "vndirect", "status": "unavailable", "error": "timeout"},
        {"provider": "yahoo-vn", "status": "unavailable", "error": "http_429"},
    ])

    assert health["status"] == "unavailable"
    assert health["availableProviders"] == 0


def test_incomplete_eod_batch_never_allows_persistence():
    result = finalize_eod_batch(
        total_symbols=10,
        successful_symbols=8,
        minimum_coverage=0.90,
        source_health={"status": "degraded"},
    )

    assert result["status"] == "incomplete"
    assert result["coverage"] == 0.8
    assert result["persist"] is False
    assert result["flags"] == ["batch_coverage_below_minimum"]


def test_complete_eod_batch_is_persistable_even_when_yahoo_is_degraded():
    result = finalize_eod_batch(
        total_symbols=10,
        successful_symbols=10,
        minimum_coverage=0.90,
        source_health={"status": "degraded"},
    )

    assert result["status"] == "degraded"
    assert result["persist"] is True


def test_eod_ingestion_buffers_then_discards_an_incomplete_universe(monkeypatch):
    from app.tasks import vietnam_market_data as task_module

    class Source:
        def __init__(self, *, history_persist):
            self.history_persist = history_persist
            self.last_kline_provider = "vndirect"
            self.last_kline_attempts = ("vndirect",)
            self.last_kline_quality = {"coverage": 1.0, "flags": []}

        def probe_daily_provider_health(self, _symbol):
            return [{"provider": "vndirect", "status": "ok", "bars": 2}]

        def get_kline(self, symbol, *_args, **_kwargs):
            if symbol == "BAD":
                self.last_kline_quality = {"coverage": 0.0, "flags": ["no_provider_bars"]}
                return []
            self.history_persist(symbol=symbol, price_mode="raw", provider="vndirect", bars=[], quality={})
            return [{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]

    recorded, persisted = [], []
    monkeypatch.setattr(task_module, "VNStockDataSource", Source)
    monkeypatch.setattr(task_module.VietnamDailyPriceRepository, "persist", lambda **payload: persisted.append(payload))
    result = task_module.ingest_hose_eod(
        symbols=["FPT", "BAD"],
        health_repository=type("Health", (), {"record": lambda _self, **payload: recorded.append(payload)})(),
    )

    assert result["status"] == "incomplete"
    assert result["persistedSymbols"] == 0
    assert persisted == []
    assert recorded[0]["result"]["coverage"] == 0.5


def test_eod_ingestion_persists_a_complete_buffer_once(monkeypatch):
    from app.tasks import vietnam_market_data as task_module

    class Source:
        def __init__(self, *, history_persist):
            self.history_persist = history_persist
            self.last_kline_provider = "vndirect"
            self.last_kline_attempts = ("vndirect", "yahoo-vn")
            self.last_kline_quality = {"coverage": 1.0, "flags": []}

        def probe_daily_provider_health(self, _symbol):
            return [
                {"provider": "vndirect", "status": "ok", "bars": 2},
                {"provider": "yahoo-vn", "status": "unavailable", "error": "http_429"},
            ]

        def get_kline(self, symbol, *_args, **_kwargs):
            self.history_persist(symbol=symbol, price_mode="raw", provider="vndirect", bars=[], quality={})
            return [{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]

    persisted = []
    monkeypatch.setattr(task_module, "VNStockDataSource", Source)
    monkeypatch.setattr(task_module.VietnamDailyPriceRepository, "persist", lambda **payload: persisted.append(payload))
    result = task_module.ingest_hose_eod(
        symbols=["FPT", "HPG"],
        health_repository=type("Health", (), {"record": lambda _self, **_payload: None})(),
    )

    assert result["status"] == "degraded"
    assert result["persistedSymbols"] == 2
    assert [item["symbol"] for item in persisted] == ["FPT", "HPG"]


def test_hose_history_backfill_reports_a_coverage_gap_without_fabricating_days(monkeypatch):
    from app.tasks import vietnam_market_data as task_module

    class Source:
        last_kline_provider = "vndirect"
        last_kline_attempts = ("vndirect",)
        last_kline_quality = {"coverage": 0.5, "flags": ["provider_history_limited"]}

        def get_kline(self, *_args, **_kwargs):
            return [{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]

    monkeypatch.setattr(task_module, "validate_hose_ai_target", lambda _market, symbol: symbol)
    result = task_module.backfill_hose_history(
        symbol="FPT", start_date="2020-01-01", end_date="2020-12-31", source=Source(),
    )

    assert result["market"] == "VNStock"
    assert result["coverage"] < 1.0
    assert result["dataGaps"] == [{"field": "dailyPrices", "reason": "HISTORICAL_COVERAGE_INCOMPLETE"}]
