"""Market-neutral evidence projection used by analysis and Copilot consumers."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from app.services.vietnam_provenance import build_hose_provenance


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _coverage(status: str, reason: str = "") -> dict[str, str | None]:
    return {"status": status, "reason": reason or None}


def _eligibility(item: Mapping[str, Any], *, require_available: bool = True) -> dict[str, Any]:
    status = str(item.get("status") or "missing")
    eligible = status == "available" if require_available else status not in {"unavailable", "missing"}
    return {"eligible": eligible, "status": status, "reason": item.get("reason") or None}


def _hose_fundamental_coverage(evidence: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, str | None]:
    """A numeric derivative alone cannot stand in for point-in-time BCTC evidence."""
    fundamentals = _mapping(evidence.get("fundamentals"))
    observations = [row for row in fundamentals.get("observations") or [] if isinstance(row, Mapping)]
    gaps = [row for row in evidence.get("dataGaps") or [] if isinstance(row, Mapping)]
    reasons = {str(row.get("reason") or "") for row in gaps if row.get("field") in {"reportScope", "fundamentalStatements"}}

    if str(base.get("status") or "") == "unavailable":
        return _coverage("unavailable", str(base.get("reason") or "PROVIDER_UNAVAILABLE"))
    if not observations:
        return _coverage("partial" if fundamentals.get("derivedMetrics") else str(base.get("status") or "missing"),
                         "NO_POINT_IN_TIME_OBSERVATIONS" if fundamentals.get("derivedMetrics") else str(base.get("reason") or "NO_POINT_IN_TIME_OBSERVATIONS"))
    if "PROVIDER_DOES_NOT_DISTINGUISH_SCOPE" in reasons or any(
        str(row.get("reportScope") or "").upper() not in {"CONSOLIDATED", "STANDALONE"}
        for row in observations
    ):
        return _coverage("partial", "PROVIDER_DOES_NOT_DISTINGUISH_SCOPE")
    if any(not row.get("periodEnd") or not row.get("availableAt") or not row.get("source") for row in observations):
        return _coverage("partial", "INCOMPLETE_POINT_IN_TIME_OBSERVATION")
    return _coverage("available")


def _generic_evidence(market: str, data: Mapping[str, Any]) -> dict[str, Any]:
    """Add a stable projection for legacy markets without changing their scoring policy."""
    payload = deepcopy(dict(data))
    price = _mapping(payload.get("price"))
    technical = _mapping(payload.get("indicators") or payload.get("technical"))
    fundamentals = _mapping(payload.get("fundamental") or payload.get("fundamentals"))
    news = list(payload.get("news") or []) if isinstance(payload.get("news"), list) else []
    context = _mapping(payload.get("macro") or payload.get("marketContext"))
    coverage = {
        "price": _coverage("available" if price else "missing", "" if price else "NO_PRICE"),
        "technical": _coverage("available" if technical else "missing", "" if technical else "NO_TECHNICAL_DATA"),
        "fundamentals": _coverage("available" if fundamentals else "missing", "" if fundamentals else "NO_FUNDAMENTALS"),
        "news": _coverage("available" if news else "missing", "" if news else "NO_RESULTS"),
        "marketContext": _coverage("available" if context else "missing", "" if context else "NO_MARKET_CONTEXT"),
    }
    return {
        "instrument": _mapping(payload.get("instrument")) or {"market": market, "symbol": payload.get("symbol")},
        "price": price,
        "technical": technical,
        "fundamentals": fundamentals,
        "corporateActions": list(payload.get("corporateActions") or []),
        "disclosures": list(payload.get("disclosures") or []),
        "news": news,
        "marketContext": context,
        "coverage": coverage,
        # Existing US/Crypto scoring remains authoritative; this is metadata only.
        "scoreEligibility": {
            "technical": _eligibility(coverage["technical"]),
            "fundamental": _eligibility(coverage["fundamentals"]),
            "sentiment": _eligibility(coverage["news"]),
            "macro": _eligibility(coverage["marketContext"]),
        },
        "dataGaps": deepcopy(list(payload.get("dataGaps") or [])),
        "sources": deepcopy(list(payload.get("sources") or [])),
    }


def build_market_research_evidence(
    market: str,
    data: Mapping[str, Any],
    *,
    fetched_at: datetime | None = None,
    news_requested: bool = False,
) -> dict[str, Any]:
    """Project collected evidence into one immutable, market-neutral contract."""
    if str(market or "") != "VNStock":
        return _generic_evidence(str(market or ""), data)

    collected = _mapping(data)
    evidence = _mapping(collected.get("vietnam_evidence"))
    if not evidence:
        evidence = {
            "instrument": {"market": "VNStock", "exchange": "HOSE", "symbol": collected.get("symbol")},
            "price": _mapping(collected.get("price")),
            "technical": _mapping(collected.get("indicators") or collected.get("technical")),
            "fundamentals": _mapping(collected.get("fundamentals")),
            "corporateActions": list(collected.get("corporateActions") or []),
            "disclosures": list(collected.get("disclosures") or []),
            "dataGaps": list(collected.get("dataGaps") or []),
            "sources": list(collected.get("sources") or []),
        }
    news = collected.get("news") if isinstance(collected.get("news"), list) else None
    provenance = build_hose_provenance(evidence, fetched_at=fetched_at, news=news, news_requested=news_requested)
    coverage = deepcopy(_mapping(provenance.get("coverage")))
    coverage["fundamentals"] = _hose_fundamental_coverage(evidence, _mapping(coverage.get("fundamentals")))
    market_context = _mapping(evidence.get("marketContext") or collected.get("macro") or collected.get("marketContext"))
    coverage["marketContext"] = _coverage("available" if market_context else "missing", "" if market_context else "NO_MARKET_CONTEXT")
    score_eligibility = {
        "technical": _eligibility(_mapping(coverage.get("technical"))),
        "fundamental": _eligibility(_mapping(coverage.get("fundamentals"))),
        "sentiment": _eligibility(_mapping(coverage.get("news"))),
        "macro": _eligibility(_mapping(coverage.get("marketContext"))),
    }
    raw_price = _mapping(evidence.get("price") or collected.get("price"))
    normalized_price = {**raw_price, **_mapping(provenance.get("price"))}
    return {
        "instrument": deepcopy(_mapping(evidence.get("instrument"))),
        "price": normalized_price,
        "technical": deepcopy(_mapping(evidence.get("technical") or collected.get("indicators") or collected.get("technical"))),
        "fundamentals": deepcopy(_mapping(evidence.get("fundamentals"))),
        "corporateActions": deepcopy(list(evidence.get("corporateActions") or [])),
        "disclosures": deepcopy(list(evidence.get("disclosures") or [])),
        "news": deepcopy(news or []),
        "marketContext": deepcopy(market_context),
        "coverage": coverage,
        "scoreEligibility": score_eligibility,
        "dataGaps": deepcopy(list(provenance.get("dataGaps") or [])),
        "sources": deepcopy(list(provenance.get("sources") or [])),
        "provenance": provenance,
    }
