from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.data_sources.vn_market_providers import (
    RequestRateGate,
    VndirectProvider,
    VietnamMarketDataSettings,
    YahooVietnamProvider,
)
from app.data_sources.vn_stock import VNStockDataSource
from app.services.vietnam_market_history import select_vietnam_daily_bars


VN_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def test_adjusted_daily_matches_provider_bars_by_vietnam_session_date():
    reference_time = int(datetime(2026, 9, 15, 7, tzinfo=VN_ZONE).timestamp())
    yahoo_time = int(datetime(2026, 9, 15, 9, tzinfo=VN_ZONE).timestamp())
    next_day = int(datetime(2026, 9, 16, 9, tzinfo=VN_ZONE).timestamp())
    reference = {
        "time": reference_time, "open": 100_000, "high": 110_000,
        "low": 90_000, "close": 100_000, "volume": 1_000,
    }
    adjusted = {
        "time": yahoo_time, "open": 100_000, "high": 110_000,
        "low": 90_000, "close": 100_000, "volume": 1_000,
        "adjusted_close": 80_000, "adjustment_factor": 0.8,
    }
    unrelated = {**adjusted, "time": next_day}

    selection = select_vietnam_daily_bars(
        [("vndirect", [reference]), ("yahoo-vn", [adjusted, unrelated])],
        "adjusted",
    )

    assert len(selection.bars) == 1
    assert selection.bars[0]["time"] == yahoo_time
    assert selection.bars[0]["close"] == 80_000
    assert selection.coverage == 1.0
    assert "outside_reference_calendar_removed" in selection.flags


class DictCache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ttl=300):
        self.values[key] = value


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_vndirect_provider_normalizes_hose_equities_and_etfs():
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/industry_classification"):
            return Response({
                "data": [
                    {
                        "industryLevel": "3",
                        "vietnameseName": "Phần mềm & Dịch vụ máy tính",
                        "codeList": "FPT,CMG",
                    },
                    {
                        "industryLevel": "4",
                        "vietnameseName": "Dịch vụ máy tính",
                        "codeList": "FPT",
                    },
                ],
                "currentPage": 1,
                "totalPages": 1,
            })
        asset_type = "ETF" if "type:ETF" in kwargs["params"]["q"] else "STOCK"
        data = [{
            "code": "E1VFVN30" if asset_type == "ETF" else "FPT",
            "type": asset_type,
            "floor": "HOSE",
            "status": "listed",
            "companyName": "Quỹ ETF VFMVN30" if asset_type == "ETF" else "CTCP FPT",
            "listedDate": "2014-10-06" if asset_type == "ETF" else "2006-12-13",
        }]
        return Response({"data": data, "currentPage": 1, "totalPages": 1})

    provider = VndirectProvider(
        settings=VietnamMarketDataSettings(timeout_seconds=7),
        http_get=get,
        rate_gate=RequestRateGate(100, 1),
    )

    rows = provider.fetch_universe()

    assert [(row.symbol, row.asset_class, row.sector, row.listed_date) for row in rows] == [
        ("FPT", "equity", "Dịch vụ máy tính", date(2006, 12, 13)),
        ("E1VFVN30", "etf", "ETF", date(2014, 10, 6)),
    ]
    assert all(
        row.exchange == "HOSE"
        and row.trading_status == "ACTIVE"
        and row.source == "vndirect"
        for row in rows
    )
    assert [call[1]["params"]["q"] for call in calls if "q" in call[1]["params"]] == [
        "type:STOCK~floor:HOSE",
        "type:ETF~floor:HOSE",
    ]


def test_vndirect_provider_normalizes_daily_and_intraday_ohlcv_to_vnd():
    calls = []
    daily_stamp = int(datetime(2026, 9, 15, tzinfo=VN_ZONE).timestamp())
    intraday_stamp = int(datetime(2026, 9, 16, 9, 5, tzinfo=VN_ZONE).timestamp())

    def get(url, **kwargs):
        calls.append((url, kwargs))
        stamp = daily_stamp if kwargs["params"]["resolution"] == "D" else intraday_stamp
        return Response({
            "s": "ok",
            "t": [stamp],
            "o": [101.0],
            "h": [103.0],
            "l": [100.0],
            "c": [102.5],
            "v": [1_250_000],
        })

    provider = VndirectProvider(
        settings=VietnamMarketDataSettings(timeout_seconds=7),
        http_get=get,
        rate_gate=RequestRateGate(100, 1),
    )

    daily = provider.fetch_ohlcv("FPT", "1D", date(2026, 9, 1), date(2026, 9, 16), 20)
    intraday = provider.fetch_ohlcv("FPT", "5m", date(2026, 9, 16), date(2026, 9, 16), 20)

    assert daily == [{
        "time": daily_stamp,
        "open": 101000.0,
        "high": 103000.0,
        "low": 100000.0,
        "close": 102500.0,
        "volume": 1250000.0,
    }]
    assert intraday[0]["time"] == intraday_stamp
    assert intraday[0]["close"] == 102500.0
    assert [call[1]["params"]["resolution"] for call in calls] == ["D", "5"]


def test_vndirect_provider_keeps_index_prices_as_points():
    stamp = int(datetime(2026, 9, 15, tzinfo=VN_ZONE).timestamp())
    provider = VndirectProvider(
        http_get=lambda *_args, **_kwargs: Response({
            "s": "ok", "t": [stamp], "o": [1260.0], "h": [1270.0],
            "l": [1255.0], "c": [1265.5], "v": [500_000_000],
        }),
        rate_gate=RequestRateGate(100, 1),
    )

    bars = provider.fetch_ohlcv("VNINDEX", "1D", date(2026, 9, 1), date(2026, 9, 16), 5)

    assert bars[0]["close"] == 1265.5


def test_vndirect_provider_skips_malformed_bar_without_losing_valid_bars():
    first_stamp = int(datetime(2026, 9, 15, tzinfo=VN_ZONE).timestamp())
    second_stamp = int(datetime(2026, 9, 16, tzinfo=VN_ZONE).timestamp())
    provider = VndirectProvider(
        http_get=lambda *_args, **_kwargs: Response({
            "s": "ok",
            "t": [first_stamp, second_stamp],
            "o": [101.0, None],
            "h": [103.0, 104.0],
            "l": [100.0, 102.0],
            "c": [102.5, 103.0],
            "v": [1_250_000, 900_000],
        }),
        rate_gate=RequestRateGate(100, 1),
    )

    bars = provider.fetch_ohlcv("FPT", "1D", date(2026, 9, 1), date(2026, 9, 16), 5)

    assert len(bars) == 1
    assert bars[0]["time"] == first_stamp
    assert bars[0]["close"] == 102500.0


def test_vn_source_falls_back_from_stale_vndirect_to_yahoo_and_caches_result():
    now = datetime(2026, 9, 16, 10, 0, tzinfo=VN_ZONE)
    stale_time = int(datetime(2026, 9, 15, 10, 0, tzinfo=VN_ZONE).timestamp())
    fresh_time = int(datetime(2026, 9, 16, 9, 55, tzinfo=VN_ZONE).timestamp())

    class Provider:
        def __init__(self, name, bars):
            self.name = name
            self.bars = bars
            self.calls = 0

        def fetch_ohlcv(self, *_args):
            self.calls += 1
            return self.bars

    stale = Provider("vndirect", [{"time": stale_time, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}])
    fresh = Provider("yahoo-vn", [{"time": fresh_time, "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2}])
    source = VNStockDataSource(providers=[stale, fresh], cache=DictCache(), now=lambda: now)

    first = source.get_kline("FPT", "5m", 10)
    second = source.get_kline("FPT", "5m", 10)

    assert first == second == fresh.bars
    assert source.last_kline_provider == "yahoo-vn"
    assert stale.calls == fresh.calls == 1


def test_vn_source_defaults_to_vndirect_then_yahoo_without_credentials():
    source = VNStockDataSource(cache=DictCache())

    assert [provider.name for provider in source.providers] == ["vndirect", "yahoo-vn"]


def test_yahoo_fallback_uses_vn_ticker_and_normalizes_chart_schema(monkeypatch):
    from app.data_sources import vn_market_providers

    stamp = int(datetime(2026, 9, 16, 14, 45, tzinfo=VN_ZONE).timestamp())

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "chart": {
                    "result": [{
                        "timestamp": [stamp],
                        "indicators": {"quote": [{
                            "open": [101_000], "high": [103_000],
                            "low": [100_000], "close": [102_500],
                            "volume": [1_250_000],
                        }]},
                    }]
                }
            }

    calls = []
    monkeypatch.setattr(
        vn_market_providers.requests,
        "get",
        lambda url, **kwargs: calls.append((url, kwargs)) or Response(),
    )
    provider = YahooVietnamProvider(rate_gate=RequestRateGate(100, 1))

    bars = provider.fetch_ohlcv("FPT", "1D", date(2026, 9, 1), date(2026, 9, 16), 5)

    assert calls[0][0].endswith("/FPT.VN")
    assert calls[0][1]["params"]["interval"] == "1d"
    assert bars == [{
        "time": stamp,
        "open": 101000.0,
        "high": 103000.0,
        "low": 100000.0,
        "close": 102500.0,
        "volume": 1250000.0,
    }]


def test_yahoo_daily_exposes_adjustment_factor_and_rejects_zero_volume_rows(monkeypatch):
    from app.data_sources import vn_market_providers

    first = int(datetime(2026, 9, 15, tzinfo=VN_ZONE).timestamp())
    holiday = int(datetime(2026, 9, 16, tzinfo=VN_ZONE).timestamp())

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "chart": {
                    "result": [{
                        "timestamp": [first, holiday],
                        "indicators": {
                            "quote": [{
                                "open": [100.0, 101.0], "high": [110.0, 102.0],
                                "low": [90.0, 100.0], "close": [100.0, 101.0],
                                "volume": [1_000.0, 0.0],
                            }],
                            "adjclose": [{"adjclose": [80.0, 80.8]}],
                        },
                    }]
                }
            }

    monkeypatch.setattr(vn_market_providers.requests, "get", lambda *_args, **_kwargs: Response())
    provider = YahooVietnamProvider(rate_gate=RequestRateGate(100, 1))

    bars = provider.fetch_ohlcv("FPT", "1D", date(2026, 9, 1), date(2026, 9, 16), 5)

    assert bars == [{
        "time": first,
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 100.0,
        "volume": 1000.0,
        "adjusted_close": 80.0,
        "adjustment_factor": 0.8,
    }]


def test_adjusted_daily_uses_vndirect_sessions_and_yahoo_adjusted_ohlc():
    first = int(datetime(2026, 9, 15, tzinfo=VN_ZONE).timestamp())
    extra = int(datetime(2026, 9, 16, tzinfo=VN_ZONE).timestamp())

    class Provider:
        def __init__(self, name, bars):
            self.name = name
            self.bars = bars
            self.calls = 0

        def fetch_ohlcv(self, *_args):
            self.calls += 1
            return [dict(item) for item in self.bars]

    vndirect = Provider("vndirect", [{
        "time": first, "open": 100_000, "high": 110_000, "low": 90_000,
        "close": 100_000, "volume": 1_000,
    }])
    yahoo = Provider("yahoo-vn", [
        {
            "time": first, "open": 100_000, "high": 110_000, "low": 90_000,
            "close": 100_000, "volume": 1_000, "adjusted_close": 80_000,
            "adjustment_factor": 0.8,
        },
        {
            "time": extra, "open": 101_000, "high": 102_000, "low": 100_000,
            "close": 101_000, "volume": 1_000, "adjusted_close": 80_800,
            "adjustment_factor": 0.8,
        },
    ])
    persisted = []
    source = VNStockDataSource(
        providers=[vndirect, yahoo], cache=DictCache(),
        now=lambda: datetime(2026, 9, 17, tzinfo=VN_ZONE),
        history_persist=lambda **payload: persisted.append(payload),
    )

    bars = source.get_kline(
        "FPT", "1D", 10,
        before_time=extra + 86_400,
        after_time=first,
        price_mode="adjusted",
    )

    assert bars == [{
        "time": first,
        "open": 80_000.0,
        "high": 88_000.0,
        "low": 72_000.0,
        "close": 80_000.0,
        "volume": 1_000,
        "price_mode": "adjusted",
    }]
    assert source.last_kline_provider == "yahoo-vn"
    assert source.last_price_mode == "adjusted"
    assert source.last_kline_quality["coverage"] == 1.0
    assert "outside_reference_calendar_removed" in source.last_kline_quality["flags"]
    assert persisted[0]["symbol"] == "FPT"
    assert persisted[0]["price_mode"] == "adjusted"
    assert persisted[0]["bars"][0]["checksum"]


def test_raw_and_adjusted_daily_cache_entries_are_isolated():
    stamp = int(datetime(2026, 9, 15, tzinfo=VN_ZONE).timestamp())

    class Provider:
        name = "yahoo-vn"

        def __init__(self):
            self.calls = 0

        def fetch_ohlcv(self, *_args):
            self.calls += 1
            return [{
                "time": stamp, "open": 100.0, "high": 100.0, "low": 100.0,
                "close": 100.0, "volume": 10.0, "adjusted_close": 80.0,
                "adjustment_factor": 0.8,
            }]

    provider = Provider()
    source = VNStockDataSource(
        providers=[provider], cache=DictCache(),
        now=lambda: datetime(2026, 9, 17, tzinfo=VN_ZONE),
        history_persist=lambda **_payload: None,
    )

    raw = source.get_kline("FPT", "1D", 10, before_time=stamp + 86_400, after_time=stamp)
    adjusted = source.get_kline(
        "FPT", "1D", 10, before_time=stamp + 86_400, after_time=stamp,
        price_mode="adjusted",
    )
    again = source.get_kline(
        "FPT", "1D", 10, before_time=stamp + 86_400, after_time=stamp,
        price_mode="adjusted",
    )

    assert raw[0]["close"] == 100.0
    assert adjusted[0]["close"] == again[0]["close"] == 80.0
    assert provider.calls == 2


def test_rate_gate_waits_when_local_provider_budget_is_exhausted():
    clock = iter([0.0, 0.0, 0.2])
    slept = []
    gate = RequestRateGate(1, 1.0, clock=lambda: next(clock), sleeper=slept.append)

    gate.acquire()
    gate.acquire()

    assert slept == [0.8]
