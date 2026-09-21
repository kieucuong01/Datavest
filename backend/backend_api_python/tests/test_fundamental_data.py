import math
from datetime import date

import pandas as pd

from app.services.fundamental_data import FundamentalDataService


def test_fundamentals_enter_panel_only_when_public_and_market_cap_can_be_derived(monkeypatch):
    service = FundamentalDataService()
    monkeypatch.setattr(
        service,
        "_load_rows",
        lambda market, symbol, end: [
            {
                "period_end": "2025-12-31",
                "available_at": "2026-01-05",
                "revenue": 500,
                "net_income": 50,
                "book_value": 300,
                "shareholder_equity": 300,
                "total_debt": 100,
                "free_cash_flow": 40,
                "shares_outstanding": 10,
                "market_cap": None,
            },
            {
                "period_end": "2026-03-31",
                "available_at": "2026-01-10",
                "revenue": 600,
                "net_income": 60,
                "book_value": 330,
                "shareholder_equity": 330,
                "total_debt": 90,
                "free_cash_flow": 45,
                "shares_outstanding": 11,
                "market_cap": 2_000,
            },
        ],
    )
    frame = pd.DataFrame(
        {"open": [100, 100, 100], "high": [100, 100, 100], "low": [100, 100, 100], "close": [100, 100, 100]},
        index=pd.to_datetime(["2026-01-01", "2026-01-05", "2026-01-10"]),
    )

    enriched = service.enrich_frame(market="USStock", symbol="AAA", frame=frame)

    assert math.isnan(enriched.loc["2026-01-01", "net_income"])
    assert enriched.loc["2026-01-05", "net_income"] == 50
    assert enriched.loc["2026-01-05", "market_cap"] == 1_000
    assert enriched.loc["2026-01-10", "net_income"] == 60
    assert enriched.loc["2026-01-10", "market_cap"] == 2_000


def test_vietnam_history_uses_evidence_observation_availability_not_current_values(monkeypatch):
    from app.services import fundamental_data as module

    evidence = {
        "fundamentals": {"observations": [{
            "metric": "revenue", "value": 500.0, "unit": "VND",
            "periodEnd": "2025-12-31", "availableAt": "2026-02-15T00:00:00+00:00",
            "frequency": "ANNUAL", "reportScope": "CONSOLIDATED", "source": "vndirect",
        }]},
        "checksum": "a" * 64,
    }
    persisted = []

    class EvidenceService:
        def build(self, **kwargs):
            assert kwargs["symbol"] == "FPT"
            assert kwargs["as_of"].tzinfo is not None
            return evidence

    monkeypatch.setattr(module, "VietnamEvidenceService", EvidenceService)
    monkeypatch.setattr(module.VietnamEvidenceRepository, "_fundamental_snapshots", lambda _value: [{
        "period_end": "2025-12-31", "available_at": "2026-02-15", "frequency": "annual",
    }])
    monkeypatch.setattr(FundamentalDataService, "upsert", staticmethod(lambda payload: persisted.append(payload)))

    result = FundamentalDataService().sync_history(market="VNStock", symbol="FPT")

    assert result == {
        "market": "VNStock", "symbol": "FPT", "observations": 1,
        "firstAvailableAt": "2026-02-15", "lastAvailableAt": "2026-02-15",
    }
    assert persisted[0]["available_at"] == date(2026, 2, 15)
    assert persisted[0]["metadata"]["pointInTime"] is True
