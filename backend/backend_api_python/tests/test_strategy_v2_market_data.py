from datetime import datetime, timedelta, timezone

from app.services.strategy_v2 import market_data


def test_market_data_normalizes_numeric_time_series_and_lowercase_timeframe(monkeypatch):
    captured = {}

    def get_kline(**kwargs):
        captured.update(kwargs)
        return [
            {
                "time": 1767225600000,
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 101,
                "volume": 10,
            },
            {
                "time": 1767240000000,
                "open": 101,
                "high": 103,
                "low": 100,
                "close": 102,
                "volume": 11,
            },
        ]

    monkeypatch.setattr(market_data.DataSourceFactory, "get_kline", get_kline)
    monkeypatch.setattr(market_data._cache, "get", lambda _key: None)
    monkeypatch.setattr(market_data._cache, "put", lambda *_args: None)

    frame = market_data.load_strategy_frame(
        "Crypto",
        "BTC/USDT",
        "4h",
        datetime(2026, 1, 1),
        datetime(2026, 1, 2),
        market_type="spot",
    )

    assert len(frame) == 2
    assert frame.index.tz is None
    assert captured["timeframe"] == "4H"
    assert captured["limit"] < 250
    assert captured["after_time"] == int(datetime(2025, 12, 31, 20, tzinfo=timezone.utc).timestamp())
    assert captured["before_time"] == int(datetime(2026, 1, 2, 4, tzinfo=timezone.utc).timestamp())


def test_four_hour_year_requests_enough_bars(monkeypatch):
    captured = {}

    def get_kline(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(market_data.DataSourceFactory, "get_kline", get_kline)
    monkeypatch.setattr(market_data._cache, "get", lambda _key: None)

    market_data.load_strategy_frame(
        "Crypto",
        "BTC/USDT",
        "4h",
        datetime(2025, 1, 1),
        datetime(2026, 1, 1),
        market_type="spot",
    )

    assert captured["limit"] > 2400


def test_market_data_normalizes_naive_and_aware_datetimes_to_utc():
    naive = datetime(2026, 7, 19, 4, 14, 13)
    shanghai = timezone(timedelta(hours=8))
    aware = datetime(2026, 7, 19, 12, 14, 13, tzinfo=shanghai)

    normalized_naive = market_data._normalize_utc_datetime(naive)
    normalized_aware = market_data._normalize_utc_datetime(aware)

    assert normalized_naive == datetime(2026, 7, 19, 4, 14, 13, tzinfo=timezone.utc)
    assert normalized_aware == normalized_naive
    assert normalized_naive.timestamp() == normalized_aware.timestamp()


def test_vietnam_daily_strategy_requests_adjusted_prices(monkeypatch):
    captured = {}

    def get_kline(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(market_data.DataSourceFactory, "get_kline", get_kline)
    monkeypatch.setattr(market_data._cache, "get", lambda _key: None)

    market_data.load_strategy_frame(
        "VNStock", "FPT", "1d",
        datetime(2021, 1, 1), datetime(2026, 1, 1),
    )

    assert captured["price_mode"] == "adjusted"


def test_vietnam_daily_strategy_adds_hose_execution_metadata(monkeypatch):
    monkeypatch.setenv("VN_LOT_SIZE", "100")
    monkeypatch.setenv("VN_SETTLEMENT_SESSIONS", "2")
    monkeypatch.setenv("VN_SELL_TAX_RATE", "0.001")

    def get_kline(**_kwargs):
        return [
            {
                "time": 1767225600,
                "open": 100,
                "high": 100,
                "low": 100,
                "close": 100,
                "volume": 100_000,
            },
            {
                "time": 1767312000,
                "open": 107,
                "high": 107,
                "low": 107,
                "close": 107,
                "volume": 100_000,
            },
        ]

    monkeypatch.setattr(market_data.DataSourceFactory, "get_kline", get_kline)
    monkeypatch.setattr(market_data._cache, "get", lambda _key: None)
    monkeypatch.setattr(market_data._cache, "put", lambda *_args: None)

    frame = market_data.load_strategy_frame(
        "VNStock", "FPT", "1d",
        datetime(2026, 1, 1), datetime(2026, 1, 3),
    )

    assert frame["lot_size"].tolist() == [100.0, 100.0]
    assert frame["settlement_sessions"].tolist() == [2, 2]
    assert frame["sell_tax_rate"].tolist() == [0.001, 0.001]
    assert frame["limit_up"].tolist() == [False, True]
