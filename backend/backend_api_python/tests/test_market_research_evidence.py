"""Normalized market evidence is the single scoring availability contract."""

from datetime import datetime, timezone
from pathlib import Path
import sys
import types

# This service is intentionally dependency-free.  Avoid importing the Flask app
# bootstrap (and its unrelated optional web dependencies) for this unit test.
_app_root = Path(__file__).resolve().parents[1] / "app"
_app_package = types.ModuleType("app")
_app_package.__path__ = [str(_app_root)]
_services_package = types.ModuleType("app.services")
_services_package.__path__ = [str(_app_root / "services")]
sys.modules.setdefault("app", _app_package)
sys.modules.setdefault("app.services", _services_package)

from app.services.market_research_evidence import build_market_research_evidence


def test_partial_hose_financial_observation_is_not_score_eligible():
    """Removing report-scope protection must make this test fail."""
    result = build_market_research_evidence(
        "VNStock",
        {
            "vietnam_evidence": {
                "instrument": {"market": "VNStock", "exchange": "HOSE", "symbol": "FPT"},
                "price": {"price": 120000, "source": "yahoo", "timeframe": "1D", "time": "2026-09-18T08:00:00Z"},
                "technical": {"rsi": {"value": 46.0}},
                "fundamentals": {
                    "observations": [{
                        "metric": "revenue", "value": 100.0, "periodEnd": "2026-06-30",
                        "availableAt": "2026-08-20T00:00:00Z", "reportScope": "UNKNOWN", "source": "vndirect",
                    }],
                    "derivedMetrics": {"pe_ratio": 12.5},
                },
                "dataGaps": [{"field": "reportScope", "reason": "PROVIDER_DOES_NOT_DISTINGUISH_SCOPE"}],
                "sources": [{"provider": "vndirect", "url": ""}],
            },
            "news": [],
            "macro": {"VNINDEX": {"price": 1300}},
        },
        fetched_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
        news_requested=True,
    )

    assert result["coverage"]["fundamentals"] == {
        "status": "partial",
        "reason": "PROVIDER_DOES_NOT_DISTINGUISH_SCOPE",
    }
    assert result["scoreEligibility"]["technical"]["eligible"] is True
    assert result["scoreEligibility"]["fundamental"] == {
        "eligible": False,
        "status": "partial",
        "reason": "PROVIDER_DOES_NOT_DISTINGUISH_SCOPE",
    }
    assert result["price"]["latencyClass"] == "eod"
    assert result["price"]["observedAt"] == "2026-09-18T08:00:00+00:00"


def test_complete_hose_evidence_is_eligible_and_preserves_observation_fields():
    """Dropping point-in-time/source fields must make this test fail."""
    result = build_market_research_evidence(
        "VNStock",
        {
            "vietnam_evidence": {
                "instrument": {"market": "VNStock", "exchange": "HOSE", "symbol": "HPG"},
                "price": {"price": 27000, "source": "yahoo", "timeframe": "1D", "time": "2026-09-18T08:00:00Z"},
                "technical": {"macd": {"signal": "bullish"}},
                "fundamentals": {
                    "observations": [{
                        "metric": "revenue", "value": 250.0, "periodEnd": "2026-06-30",
                        "availableAt": "2026-08-20T00:00:00Z", "reportScope": "CONSOLIDATED", "source": "vndirect",
                    }],
                    "derivedMetrics": {"roe": 0.21},
                },
                "corporateActions": [{"eventType": "DIVIDEND"}],
                "disclosures": [{"eventType": "FINANCIAL_REPORT"}],
                "sources": [{"provider": "vndirect", "url": ""}],
            },
            "news": [{"title": "Kết quả kinh doanh"}],
            "macro": {"VNINDEX": {"price": 1300}},
        },
        fetched_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
        news_requested=True,
    )

    assert result["coverage"]["fundamentals"]["status"] == "available"
    assert result["scoreEligibility"]["fundamental"]["eligible"] is True
    assert result["fundamentals"]["observations"][0]["periodEnd"] == "2026-06-30"
    assert result["fundamentals"]["observations"][0]["availableAt"] == "2026-08-20T00:00:00Z"
    assert result["fundamentals"]["observations"][0]["source"] == "vndirect"


def test_generic_market_projection_is_additive_and_does_not_mutate_payload():
    """Changing an existing generic payload while normalizing it must fail here."""
    payload = {
        "instrument": {"market": "USStock", "symbol": "AAPL"},
        "price": {"price": 200.0, "source": "yahoo"},
        "indicators": {"rsi": {"value": 55.0}},
        "fundamental": {"pe_ratio": 25.0},
        "news": [{"title": "Earnings"}],
        "macro": {"SPY": {"price": 500.0}},
    }

    result = build_market_research_evidence("USStock", payload, fetched_at=datetime(2026, 9, 21, tzinfo=timezone.utc))

    assert result["instrument"] == {"market": "USStock", "symbol": "AAPL"}
    assert result["scoreEligibility"]["fundamental"]["eligible"] is True
    assert payload == {
        "instrument": {"market": "USStock", "symbol": "AAPL"},
        "price": {"price": 200.0, "source": "yahoo"},
        "indicators": {"rsi": {"value": 55.0}},
        "fundamental": {"pe_ratio": 25.0},
        "news": [{"title": "Earnings"}],
        "macro": {"SPY": {"price": 500.0}},
    }
