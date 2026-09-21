"""Source observation and fetch time must never be conflated."""

from datetime import datetime, timezone
from pathlib import Path
import sys
import types

_app_root = Path(__file__).resolve().parents[1] / "app"
_app_package = types.ModuleType("app")
_app_package.__path__ = [str(_app_root)]
_services_package = types.ModuleType("app.services")
_services_package.__path__ = [str(_app_root / "services")]
sys.modules.setdefault("app", _app_package)
sys.modules.setdefault("app.services", _services_package)

from app.services.vietnam_provenance import build_hose_provenance


def test_daily_bar_is_eod_with_separate_observation_and_fetch_times():
    result = build_hose_provenance({
        "instrument": {"exchange": "HOSE"},
        "price": {"price": 120000, "source": "yahoo", "timeframe": "1D", "time": "2026-09-18T08:00:00Z"},
    }, fetched_at=datetime(2026, 9, 21, tzinfo=timezone.utc))

    assert result["exchange"] == "HOSE"
    assert result["currency"] == "VND"
    assert result["price"]["latencyClass"] == "eod"
    assert result["price"]["observedAt"] == "2026-09-18T08:00:00+00:00"
    assert result["price"]["fetchedAt"] == "2026-09-21T00:00:00+00:00"


def test_fresh_fetch_without_verified_latency_stays_unknown():
    result = build_hose_provenance({
        "instrument": {"exchange": "HOSE"},
        "price": {"price": 120000, "source": "vndirect"},
    }, fetched_at=datetime(2026, 9, 21, tzinfo=timezone.utc))

    assert result["price"]["latencyClass"] == "unknown"
    assert result["price"]["observedAt"] is None
    assert result["price"]["fetchedAt"] is not None


def test_explicit_provider_delay_is_accepted_only_when_verified():
    result = build_hose_provenance({
        "price": {"price": 10, "source": "vndirect", "latencyClass": "delayed", "delayMinutes": 15,
                  "latencyVerified": True},
    })
    assert result["price"]["latencyClass"] == "delayed"
    assert result["price"]["delayMinutes"] == 15

    unverified = build_hose_provenance({
        "price": {"price": 10, "source": "vndirect", "latencyClass": "real_time"},
    })
    assert unverified["price"]["latencyClass"] == "unknown"


def test_absent_statements_news_and_technical_are_explicit_gaps():
    result = build_hose_provenance({"price": {"price": 10}, "technical": {}, "fundamentals": {}})
    assert result["coverage"]["fundamentals"]["status"] == "missing"
    assert result["coverage"]["technical"]["status"] == "missing"
    assert result["coverage"]["news"]["status"] == "not_requested"
    assert build_hose_provenance({}, news_requested=True)["coverage"]["news"]["status"] == "unavailable"
    assert {gap["field"] for gap in result["dataGaps"]} >= {"fundamentals", "technical"}


def test_daily_ticker_carries_bar_time_and_timeframe():
    from app.data_sources.vn_stock import VNStockDataSource

    source = object.__new__(VNStockDataSource)
    source.get_kline = lambda symbol, timeframe, limit: [
        {"time": 1789747200, "open": 100, "high": 110, "low": 90, "close": 105},
    ]
    source.last_kline_provider = "yahoo"

    quote = source.get_ticker("FPT")

    assert quote["timeframe"] == "1D"
    assert quote["time"] == 1789747200
    assert quote["provider"] == "yahoo"


def test_indicator_error_is_not_available_technical_evidence():
    result = build_hose_provenance({
        "price": {"price": 120000},
        "technical": {"error": "Insufficient data", "current_price": 120000},
    })
    assert result["coverage"]["technical"]["status"] == "missing"


def test_unknown_or_incomplete_financial_observations_are_partial_not_available():
    """Treating a partial BCTC as fully available must make this test fail."""
    result = build_hose_provenance({
        "fundamentals": {
            "observations": [{
                "metric": "revenue", "value": 100.0, "periodEnd": "2026-06-30",
                "availableAt": "2026-08-20T00:00:00Z", "reportScope": "UNKNOWN", "source": "vndirect",
            }],
            "derivedMetrics": {"pe_ratio": 12.5},
        },
    })

    assert result["coverage"]["fundamentals"] == {
        "status": "partial",
        "reason": "PROVIDER_DOES_NOT_DISTINGUISH_SCOPE",
    }
