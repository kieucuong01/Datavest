from datetime import datetime, timezone


UTC = timezone.utc


class FakeBinanceClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, params):
        self.calls.append((path, dict(params)))
        return self.responses.pop(0)


def test_binance_backfill_aggregates_multiple_funding_windows_into_one_daily_point():
    from app.services.smart_insights.binance_usdm_derivatives import BinanceUsdmDerivativesCollector
    from app.services.smart_insights.derivatives import DerivativeBackfillRequest, FUNDING_ANNUALIZED, OI_USD, TAKER_IMBALANCE

    client = FakeBinanceClient([
        [{"fundingRate": "0.0001", "fundingTime": "1788048000000"}, {"fundingRate": "-0.0002", "fundingTime": "1788076800000"}],
        [["1788048000000", "0", "0", "0", "100", "0"]],
        [{"sumOpenInterestValue": "1000000", "timestamp": "1788048000000"}],
        [{"buySellRatio": "1.5", "timestamp": "1788048000000"}],
    ])
    request = DerivativeBackfillRequest("binance-usdm-derivatives", ("BTC",), datetime(2026, 8, 29, tzinfo=UTC), datetime(2026, 8, 30, tzinfo=UTC))

    rows, coverage = BinanceUsdmDerivativesCollector(client=client).backfill(request)

    funding = [row for row in rows if row.value["metric"] == FUNDING_ANNUALIZED]
    assert len(funding) == 1
    assert funding[0].value["value"] == "-0.0365"
    assert {row.value["metric"] for row in rows} == {FUNDING_ANNUALIZED, "crypto.derivatives.perpetual.price_usd", OI_USD, TAKER_IMBALANCE}
    assert {item.metric for item in coverage if item.history_limited} == {OI_USD, TAKER_IMBALANCE}


def test_binance_rejects_non_numeric_open_interest_instead_of_storing_zero():
    import pytest
    from app.services.smart_insights.binance_usdm_derivatives import BinanceUsdmDerivativesCollector, BinanceUsdmDerivativesUnavailable
    from app.services.smart_insights.derivatives import DerivativeBackfillRequest

    client = FakeBinanceClient([[], [], [{"sumOpenInterestValue": None, "timestamp": "1788048000000"}]])
    request = DerivativeBackfillRequest("binance-usdm-derivatives", ("BTC",), datetime(2026, 8, 29, tzinfo=UTC), datetime(2026, 8, 30, tzinfo=UTC))

    with pytest.raises(BinanceUsdmDerivativesUnavailable, match="INVALID_OPEN_INTEREST"):
        BinanceUsdmDerivativesCollector(client=client).backfill(request)
