"""Point-in-time HOSE evidence used by TradingAgents runs."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone

import pytest


def _daily_bars() -> list[dict]:
    start = datetime(2026, 8, 8, 3, tzinfo=timezone.utc)
    rows = []
    for index in range(41):
        price = 100.0 + index
        rows.append({
            "time": int((start + timedelta(days=index)).timestamp()),
            "open": price - 1,
            "high": price + 1,
            "low": price - 2,
            "close": price,
            "volume": 100_000 + index,
            "source": "vndirect+yahoo",
        })
    return rows


def test_builder_uses_adjusted_bars_and_excludes_rows_after_analysis_date(monkeypatch):
    from app.services import trading_agents_vietnam as module

    captured: dict = {}

    def get_kline(**kwargs):
        captured["kline"] = kwargs
        return _daily_bars()

    class EvidenceService:
        def build(self, **kwargs):
            captured["evidence"] = kwargs
            return {
                "version": "vietnam-evidence-v1",
                "asOf": kwargs["as_of"].isoformat(),
                "instrument": {"market": "VNStock", "exchange": "HOSE", "symbol": kwargs["symbol"]},
                "price": kwargs["price"],
                "technical": kwargs["technical"],
                "fundamentals": {"observations": [], "derivedMetrics": {}},
                "corporateActions": [],
                "disclosures": [],
                "marketContext": {},
                "dataGaps": [],
                "sources": [],
                "checksum": "a" * 64,
            }

    monkeypatch.setattr(module.DataSourceFactory, "get_kline", get_kline)
    monkeypatch.setattr(module, "get_vietnam_evidence_service", lambda: EvidenceService())

    evidence = module.build_trading_agents_vietnam_evidence("fpt.vn", "2026-09-16")

    assert captured["kline"]["market"] == "VNStock"
    assert captured["kline"]["symbol"] == "FPT"
    assert captured["kline"]["timeframe"] == "1D"
    assert captured["kline"]["price_mode"] == "adjusted"
    assert captured["evidence"]["as_of"].isoformat() == "2026-09-16T16:59:59.999999+00:00"
    assert evidence["price"] == {
        "price": 139.0,
        "open": 138.0,
        "high": 140.0,
        "low": 137.0,
        "volume": 100_039.0,
        "time": _daily_bars()[39]["time"],
        "source": "vndirect+yahoo",
        "priceMode": "adjusted",
    }
    assert evidence["technical"]["current_price"] == 139.0


def test_builder_fails_closed_when_no_price_exists_on_or_before_cutoff(monkeypatch):
    from app.services import trading_agents_vietnam as module

    future = {
        "time": int(datetime(2026, 9, 17, 3, tzinfo=timezone.utc).timestamp()),
        "open": 100,
        "high": 101,
        "low": 99,
        "close": 100,
        "volume": 10,
    }
    monkeypatch.setattr(module.DataSourceFactory, "get_kline", lambda **_kwargs: [future])

    with pytest.raises(module.TradingAgentsVietnamEvidenceUnavailable, match="price history"):
        module.build_trading_agents_vietnam_evidence("FPT", "2026-09-16")


def test_builder_rejects_invalid_analysis_date_before_calling_providers(monkeypatch):
    from app.services import trading_agents_vietnam as module

    monkeypatch.setattr(
        module.DataSourceFactory,
        "get_kline",
        lambda **_kwargs: pytest.fail("provider must not be called"),
    )

    with pytest.raises(module.TradingAgentsVietnamEvidenceUnavailable, match="analysis date"):
        module.build_trading_agents_vietnam_evidence("FPT", "not-a-date")


def test_builder_compacts_large_fundamental_snapshot_for_private_runtime(monkeypatch):
    from app.services import trading_agents_vietnam as module

    observations = []
    for period in range(100):
        period_end = date(2000, 1, 1) + timedelta(days=90 * period)
        for metric in range(20):
            observations.append({
                "metric": f"metric_{metric}",
                "value": period * 20 + metric,
                "frequency": "QUARTERLY",
                "reportScope": "CONSOLIDATED",
                "periodEnd": period_end.isoformat(),
                "availableAt": (period_end + timedelta(days=45)).isoformat() + "T00:00:00+00:00",
                "source": "vndirect",
                "sourceUrl": "https://example.com/" + "x" * 220,
            })
    full_evidence = {
        "version": "vietnam-evidence-v1",
        "asOf": "2026-09-16T16:59:59.999999+00:00",
        "instrument": {"market": "VNStock", "exchange": "HOSE", "symbol": "FPT"},
        "price": {"price": 139.0, "source": "yahoo-vn"},
        "technical": {"current_price": 139.0},
        "fundamentals": {"observations": observations, "derivedMetrics": {"pe_ratio": 12.0}},
        "corporateActions": [{"availableAt": "2025-01-01T00:00:00+00:00", "type": "dividend"}],
        "disclosures": [],
        "marketContext": {},
        "dataGaps": [],
        "sources": [{"provider": "vndirect", "url": "https://example.com"}],
    }
    full_evidence["checksum"] = hashlib.sha256(
        json.dumps(full_evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert len(json.dumps(full_evidence).encode("utf-8")) > 512 * 1024

    class EvidenceService:
        def build(self, **_kwargs):
            return full_evidence

    monkeypatch.setattr(module.DataSourceFactory, "get_kline", lambda **_kwargs: _daily_bars())
    monkeypatch.setattr(module, "get_vietnam_evidence_service", lambda: EvidenceService())

    evidence = module.build_trading_agents_vietnam_evidence("FPT", "2026-09-16")

    serialized = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert len(serialized.encode("utf-8")) <= 512 * 1024
    assert 0 < len(evidence["fundamentals"]["observations"]) < len(observations)
    assert {row["metric"] for row in evidence["fundamentals"]["observations"]} == {
        f"metric_{index}" for index in range(20)
    }
    assert evidence["fundamentals"]["derivedMetrics"] == {"pe_ratio": 12.0}
    assert evidence["corporateActions"] == full_evidence["corporateActions"]
    assert evidence["sources"] == full_evidence["sources"]
    assert {gap["reason"] for gap in evidence["dataGaps"]} == {"AGENT_SNAPSHOT_COMPACTED"}
    unsigned = dict(evidence)
    checksum = unsigned.pop("checksum")
    assert checksum == hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert len(full_evidence["fundamentals"]["observations"]) == 2000
