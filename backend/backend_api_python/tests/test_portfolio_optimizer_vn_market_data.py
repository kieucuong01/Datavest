"""Vietnam optimizer inputs use the shared VNDIRECT/Yahoo adapter."""

from datetime import date, datetime, time, timezone

import pytest

from app.services.portfolio_optimizer.market_data import Instrument
from app.services.portfolio_optimizer.quantdinger_gateway import QuantDingerOptimizerGateway


def unix(day: date, *, end=False):
    return int(datetime.combine(day, time.max if end else time.min, tzinfo=timezone.utc).timestamp())


class FakeVNSource:
    def __init__(self, bars, provider="yahoo-vn", attempts=("vndirect", "yahoo-vn")):
        self.bars = bars
        self.last_kline_provider = provider
        self.last_kline_attempts = attempts
        self.calls = []

    def get_kline(
        self, symbol, timeframe, limit, before_time=None, after_time=None, *, price_mode="raw"
    ):
        self.calls.append((symbol, timeframe, limit, before_time, after_time, price_mode))
        return self.bars


def test_vn_daily_uses_shared_adapter_and_preserves_winning_fallback_provider():
    source = FakeVNSource([
        {"time": unix(date(2025, 1, 2)), "close": 101250.0},
        {"time": unix(date(2025, 1, 3)), "close": 102500.0},
    ])
    gateway = QuantDingerOptimizerGateway(vn_source_factory=lambda: source)

    series = gateway.fetch_daily(
        Instrument(market="VNStock", symbol="FPT", currency="VND"),
        start_date="2025-01-02",
        end_date="2025-01-03",
    )

    assert source.calls == [(
        "FPT", "1D", 31, unix(date(2025, 1, 3), end=True) + 1,
        unix(date(2025, 1, 2)), "total_return",
    )]
    assert series.closes == (101250.0, 102500.0)
    assert series.provider == "yahoo-vn"
    assert series.fallback_chain == ("vndirect", "yahoo-vn")
    assert series.price_unit == "VND"
    assert series.mark_to_market_supported is True
    assert series.price_mode == "total_return"


def test_vn_optimizer_rejects_undercovered_history():
    source = FakeVNSource([
        {"time": unix(date(2025, 1, 2)), "close": 101250.0},
        {"time": unix(date(2025, 1, 3)), "close": 102500.0},
    ])
    source.last_kline_quality = {"coverage": 0.50, "flags": ["large_gap"]}
    source.last_price_mode = "total_return"
    gateway = QuantDingerOptimizerGateway(vn_source_factory=lambda: source)

    with pytest.raises(ValueError, match="vn_market_data_unavailable: insufficient_coverage"):
        gateway.fetch_daily(
            Instrument(market="VNStock", symbol="FPT", currency="VND"),
            start_date="2025-01-02", end_date="2025-01-03",
        )


def test_vn_index_keeps_index_points_semantics():
    source = FakeVNSource([{"time": unix(date(2025, 1, 2)), "close": 1263.5}], provider="vndirect", attempts=("vndirect",))
    gateway = QuantDingerOptimizerGateway(vn_source_factory=lambda: source)

    series = gateway.fetch_daily(
        Instrument(market="VNStock", symbol="VNINDEX", currency="VND"),
        start_date="2025-01-02",
        end_date="2025-01-02",
    )

    assert series.price_unit == "INDEX_POINTS"
    assert series.mark_to_market_supported is False


@pytest.mark.parametrize(
    ("instrument", "start_date", "end_date", "error"),
    [
        ({"symbol": "../FPT", "currency": "VND"}, "2025-01-02", "2025-01-03", "invalid_symbol"),
        ({"symbol": "FPT", "currency": "USD"}, "2025-01-02", "2025-01-03", "invalid_currency"),
        ({"symbol": "FPT", "currency": "VND"}, "2025-01-03", "2025-01-02", "invalid_date_range"),
    ],
)
def test_vn_daily_fails_closed_for_invalid_inputs(instrument, start_date, end_date, error):
    gateway = QuantDingerOptimizerGateway(vn_source_factory=lambda: FakeVNSource([]))
    with pytest.raises(ValueError, match=f"vn_market_data_unavailable: {error}"):
        gateway.fetch_daily(Instrument(market="VNStock", **instrument), start_date=start_date, end_date=end_date)


def test_vn_daily_fails_closed_when_all_free_providers_return_no_bars():
    gateway = QuantDingerOptimizerGateway(vn_source_factory=lambda: FakeVNSource([], provider="", attempts=("vndirect", "yahoo-vn")))

    with pytest.raises(ValueError, match="vn_market_data_unavailable: no_bars"):
        gateway.fetch_daily(
            Instrument(market="VNStock", symbol="FPT", currency="VND"),
            start_date="2025-01-02",
            end_date="2025-01-03",
        )
