from datetime import datetime, timezone


UTC = timezone.utc


def test_daily_effective_at_is_the_previous_utc_day():
    from app.services.smart_insights.derivatives import daily_effective_at

    assert daily_effective_at(datetime(2026, 8, 31, 0, 40, tzinfo=UTC)) == datetime(
        2026, 8, 30, tzinfo=UTC
    )


def test_coverage_preserves_documented_history_limit():
    from app.services.smart_insights.derivatives import DerivativeCoverage, OI_USD

    coverage = DerivativeCoverage(
        source="binance-usdm-derivatives",
        metric=OI_USD,
        symbol="BTC",
        start=datetime(2026, 8, 1, tzinfo=UTC),
        end=datetime(2026, 8, 31, tzinfo=UTC),
        history_limited=True,
    )

    assert coverage.as_dict() == {
        "source": "binance-usdm-derivatives",
        "metric": OI_USD,
        "symbol": "BTC",
        "start": "2026-08-01T00:00:00+00:00",
        "end": "2026-08-31T00:00:00+00:00",
        "historyLimited": True,
    }


def test_core_derivatives_sources_are_registered_as_runtime_api_sources():
    from app.services.smart_insights.sources import SOURCES

    for code in ("bybit-derivatives", "binance-usdm-derivatives", "deribit-public-derivatives"):
        source = SOURCES[code]
        assert source.market == "crypto"
        assert source.collection_mode == "API"
        assert source.schedule == "daily"
