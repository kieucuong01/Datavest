from datetime import datetime, timezone

import pytest


UTC = timezone.utc


class FakeBybitClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, path, params):
        self.calls.append((path, dict(params)))
        return self.pages.pop(0)


def test_bybit_open_interest_backfill_follows_cursor_and_emits_utc_daily_rows():
    from app.services.smart_insights.bybit_derivatives import BybitDerivativesCollector
    from app.services.smart_insights.derivatives import DerivativeBackfillRequest, OI_NATIVE

    client = FakeBybitClient([
        {"result": {"list": [{"openInterest": "10", "timestamp": "1788048000000"}], "nextPageCursor": "next"}},
        {"result": {"list": [{"openInterest": "11", "timestamp": "1788134400000"}], "nextPageCursor": ""}},
    ])
    request = DerivativeBackfillRequest(
        source="bybit-derivatives",
        symbols=("BTC",),
        start=datetime(2026, 8, 29, tzinfo=UTC),
        end=datetime(2026, 8, 31, tzinfo=UTC),
    )

    rows, coverage = BybitDerivativesCollector(client=client).backfill_open_interest(request)

    assert [row.value["metric"] for row in rows] == [OI_NATIVE, OI_NATIVE]
    assert [row.effective_at.date().isoformat() for row in rows] == ["2026-08-30", "2026-08-31"]
    assert coverage[0].history_limited is False
    assert client.calls[1][1]["cursor"] == "next"


def test_bybit_collector_rejects_missing_open_interest_instead_of_storing_zero():
    from app.services.smart_insights.bybit_derivatives import BybitDerivativesCollector, BybitDerivativesUnavailable
    from app.services.smart_insights.derivatives import DerivativeBackfillRequest

    request = DerivativeBackfillRequest(
        source="bybit-derivatives", symbols=("BTC",),
        start=datetime(2026, 8, 29, tzinfo=UTC), end=datetime(2026, 8, 31, tzinfo=UTC),
    )
    client = FakeBybitClient([{"result": {"list": [{"openInterest": None, "timestamp": "1788048000000"}]}}])

    with pytest.raises(BybitDerivativesUnavailable, match="INVALID_OPEN_INTEREST"):
        BybitDerivativesCollector(client=client).backfill_open_interest(request)
