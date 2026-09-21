"""Deterministic data availability and market-time provenance for HOSE evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _instant(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, (int, float)):
            stamp = float(value)
            parsed = datetime.fromtimestamp(stamp / 1000 if abs(stamp) > 10**11 else stamp, tz=timezone.utc)
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _coverage(status: str, reason: str = "") -> dict[str, str | None]:
    return {"status": status, "reason": reason or None}


def build_hose_provenance(
    evidence: Mapping[str, Any],
    *,
    fetched_at: datetime | None = None,
    news: list[dict] | None = None,
    news_requested: bool = False,
) -> dict[str, Any]:
    """Project only verified source, time, latency and coverage from evidence."""
    evidence = evidence or {}
    price = evidence.get("price") if isinstance(evidence.get("price"), dict) else {}
    technical = evidence.get("technical") if isinstance(evidence.get("technical"), dict) else {}
    fundamentals = evidence.get("fundamentals") if isinstance(evidence.get("fundamentals"), dict) else {}
    old_provenance = evidence.get("provenance") if isinstance(evidence.get("provenance"), dict) else {}
    old_price = old_provenance.get("price") if isinstance(old_provenance.get("price"), dict) else {}

    has_price = False
    try:
        has_price = float(price.get("price")) > 0
    except (TypeError, ValueError, OverflowError):
        pass
    timeframe = str(price.get("timeframe") or "").upper()
    verified_latency = str(price.get("latencyClass") or "").lower() if price.get("latencyVerified") is True else ""
    latency = (
        "eod" if has_price and timeframe == "1D"
        else verified_latency if has_price and verified_latency in {"real_time", "delayed"}
        else "unknown"
    )
    delay = price.get("delayMinutes") if latency == "delayed" else None
    if not isinstance(delay, (int, float)) or delay < 0:
        delay = None

    observations = fundamentals.get("observations") or []
    derived = fundamentals.get("derivedMetrics") or {}
    has_fundamentals = bool(observations) or any(
        value is not None for key, value in derived.items() if key != "ratioUnit"
    )
    has_technical = any(
        bool(technical.get(key))
        for key in ("rsi", "macd", "moving_averages", "levels", "signals", "timeframes")
    )
    existing_gaps = [dict(item) for item in evidence.get("dataGaps") or [] if isinstance(item, dict)]
    unavailable = {item.get("field") for item in existing_gaps if item.get("reason") == "PROVIDER_UNAVAILABLE"}
    incomplete_observation = any(
        not row.get("periodEnd") or not row.get("availableAt") or not row.get("source")
        for row in observations if isinstance(row, dict)
    )
    unknown_scope = any(
        str(row.get("reportScope") or "").upper() not in {"CONSOLIDATED", "STANDALONE"}
        for row in observations if isinstance(row, dict)
    )
    fundamental_state = (
        _coverage("unavailable", "PROVIDER_UNAVAILABLE") if "fundamentalStatements" in unavailable
        else _coverage("partial", "PROVIDER_DOES_NOT_DISTINGUISH_SCOPE") if observations and unknown_scope
        else _coverage("partial", "INCOMPLETE_POINT_IN_TIME_OBSERVATION") if observations and incomplete_observation
        else _coverage("available") if observations
        else _coverage("partial", "NO_POINT_IN_TIME_OBSERVATIONS") if has_fundamentals
        else _coverage("missing", "NO_POINT_IN_TIME_OBSERVATIONS")
    )
    coverage = {
        "price": _coverage("available" if has_price else "missing", "" if has_price else "NO_PRICE"),
        "technical": _coverage("available" if has_technical else "missing", "" if has_technical else "NO_TECHNICAL_DATA"),
        "fundamentals": fundamental_state,
        "news": _coverage(
            "not_requested" if not news_requested else "unavailable" if news is None else "available" if news else "missing",
            "" if not news_requested or news else "NOT_CAPTURED" if news is None else "NO_RESULTS",
        ),
        "corporateActions": _coverage("available" if evidence.get("corporateActions") else "missing", "" if evidence.get("corporateActions") else "NO_EVENTS_CAPTURED"),
        "disclosures": _coverage("available" if evidence.get("disclosures") else "missing", "" if evidence.get("disclosures") else "NO_DISCLOSURES_CAPTURED"),
    }
    gaps = existing_gaps.copy()
    seen = {(item.get("field"), item.get("reason")) for item in gaps}
    for field, state in coverage.items():
        if state["status"] not in {"missing", "unavailable"}:
            continue
        item = {"field": field, "reason": state["reason"]}
        if (item["field"], item["reason"]) not in seen:
            gaps.append(item)
            seen.add((item["field"], item["reason"]))

    instrument = evidence.get("instrument") if isinstance(evidence.get("instrument"), dict) else {}
    source = str(price.get("source") or "").strip() or "unknown"
    sources = [dict(item) for item in evidence.get("sources") or [] if isinstance(item, dict)]
    if source != "unknown" and not any(item.get("provider") == source for item in sources):
        sources.append({"provider": source, "url": ""})
    return {
        "exchange": str(instrument.get("exchange") or "HOSE"),
        "currency": "VND",
        "price": {
            "source": source,
            "observedAt": _instant(price.get("time") or price.get("timestamp") or price.get("observedAt")),
            "fetchedAt": _instant(fetched_at) or _instant(old_price.get("fetchedAt")),
            "latencyClass": latency,
            "delayMinutes": delay,
        },
        "coverage": coverage,
        "dataGaps": gaps,
        "sources": sources,
    }
