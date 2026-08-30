"""Safe read models for a user's one-time legacy DataVest import.

The source export is retained as JSONB for migration lineage, not exposed as a
raw API.  These helpers map only the fields that the Smart Insights UI needs.
"""

from __future__ import annotations

from typing import Any, Mapping


_METHODOLOGY = "datavest-production-account-import-v1"
_CRYPTO_SYMBOLS = frozenset({"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "USDT", "USDC"})
_VN_INDEXES = frozenset({"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"})


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _items(value: Any) -> list[Mapping[str, Any]]:
    return [_mapping(item) for item in value] if isinstance(value, list) else []


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None


def _market_for_symbol(symbol: str) -> str:
    normalized = symbol.upper().replace("/USDT", "").replace("-USD", "")
    if normalized in _CRYPTO_SYMBOLS:
        return "crypto"
    if normalized.startswith(("XAU", "GOLD")):
        return "gold"
    if normalized in _VN_INDEXES or (len(normalized) == 3 and normalized.isalpha()):
        return "vn"
    return "us"


def _checksum_id(checksum: str) -> str:
    return str(checksum or "legacy-import")[:24]


def _safe_opinion(item: Mapping[str, Any], *, ordinal: int) -> dict[str, Any] | None:
    symbol = str(item.get("symbol") or "").strip().upper()
    if not symbol or len(symbol) > 32:
        return None
    opinion_market = _market_for_symbol(symbol)
    display_symbol = symbol
    if opinion_market == "crypto":
        display_symbol = symbol.split("/", 1)[0].split("-", 1)[0]
    elif opinion_market == "gold":
        display_symbol = "XAU"
    thesis = str(item.get("thesis") or "").strip()
    if len(thesis) > 4000:
        thesis = thesis[:4000]
    evidence = item.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    evidence_validated = bool(item.get("evidenceValidated")) and bool(evidence)
    return {
        "id": f"legacy-opinion-{ordinal}-{symbol.lower()}",
        "symbol": display_symbol,
        "assetName": str(item.get("assetName") or display_symbol)[:160],
        "market": opinion_market,
        "stance": str(item.get("stance") or "NEUTRAL")[:80],
        "score": _number(item.get("quantScore")),
        "confidence": _number(item.get("confidence")),
        "portfolioWeightPct": _number(item.get("portfolioWeightPct")),
        "rationale": {"warning": "Imported production briefing; legacy evidence IDs are not exposed as local evidence."},
        # A legacy thesis is not sufficient proof for an AI explanation. Only
        # pass it through when the imported record explicitly carries validated
        # evidence alongside it.
        "explanation": thesis or None if evidence_validated else None,
        "explanationModel": None,
        "evidenceValidated": evidence_validated,
        "dataClass": "LIVE",
        "evidence": evidence if evidence_validated else [],
    }


def _safe_change(item: Mapping[str, Any], *, ordinal: int) -> dict[str, Any] | None:
    symbol = str(item.get("symbol") or "").strip().upper()
    if not symbol or len(symbol) > 32:
        return None
    reason = str(item.get("reason") or "").strip()
    return {
        "id": f"legacy-change-{ordinal}-{symbol.lower()}",
        "symbol": symbol,
        "assetName": str(item.get("assetName") or symbol)[:160],
        "changeType": str(item.get("changeType") or "")[:80],
        "reason": reason[:4000] or None,
        "value": _number(item.get("scoreDelta")),
        "currentAction": str(item.get("currentAction") or "")[:80] or None,
        "previousAction": str(item.get("previousAction") or "")[:80] or None,
    }


def _safe_primary(value: Any) -> dict[str, Any]:
    primary = _mapping(value)
    result: dict[str, Any] = {}
    for key in ("title", "subtitle", "thesis", "status", "summary"):
        text = primary.get(key)
        if isinstance(text, (str, int, float, bool)):
            result[key] = str(text)[:4000]
    return result


def _safe_risk_alert(value: Mapping[str, Any], *, ordinal: int) -> dict[str, Any] | None:
    symbol = str(value.get("symbol") or "").strip().upper()
    message = str(value.get("message") or value.get("reason") or "").strip()
    if not symbol and not message:
        return None
    return {
        "id": f"legacy-risk-{ordinal}-{symbol.lower() or 'portfolio'}",
        "symbol": symbol or None,
        "severity": str(value.get("severity") or value.get("level") or "unknown")[:40],
        "message": message[:4000] or None,
    }


def _safe_portfolio_state(value: Any) -> dict[str, Any]:
    state = _mapping(value)
    result: dict[str, Any] = {}
    for key in ("dataAsOf", "currency", "portfolioId", "portfolioName"):
        raw = state.get(key)
        if isinstance(raw, (str, int, float, bool)):
            result[key] = str(raw)[:160]
    for key in ("totalValue", "cash", "investedValue", "returnPct"):
        number = _number(state.get(key))
        if number is not None:
            result[key] = number
    return result


def build_imported_overview(
    payload: Mapping[str, Any],
    *,
    checksum: str,
    market: str,
    watchlist_pairs: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a bounded public view of a tenant's imported production briefing."""
    briefing = _mapping(payload)
    opinions = [
        opinion
        for ordinal, item in enumerate(_items(briefing.get("assetOpinions")), start=1)
        if (opinion := _safe_opinion(item, ordinal=ordinal)) is not None
    ]
    if market != "all":
        opinions = [opinion for opinion in opinions if opinion["market"] == market]
    if watchlist_pairs is not None:
        from .watchlist_scope import filter_opinions_to_watchlist

        opinions = list(filter_opinions_to_watchlist(opinions, watchlist_pairs))
    changes = [
        change
        for ordinal, item in enumerate(_items(briefing.get("portfolioChanges")), start=1)
        if (change := _safe_change(item, ordinal=ordinal)) is not None
    ]
    risk_alerts = [
        alert
        for ordinal, item in enumerate(_items(briefing.get("riskAlerts")), start=1)
        if (alert := _safe_risk_alert(item, ordinal=ordinal)) is not None
    ]
    return {
        "id": f"production-import-{_checksum_id(checksum)}",
        "asOf": str(briefing.get("localDate") or "") or None,
        "market": market,
        "mode": "live",
        "status": "PARTIAL",
        "methodologyVersion": _METHODOLOGY,
        "evidenceChecksum": str(checksum or "") or None,
        "summary": {
            "sources": ["datavest-production-import"],
            "metrics": ["legacy.asset_opinions", "legacy.portfolio_changes"],
            "sourceCount": 1,
            "metricCount": 2,
            "observationCount": len(opinions),
            "directionalModelStatus": "UNAVAILABLE",
            "overallDataConfidence": _number(briefing.get("overallDataConfidence")),
        },
        "primary": _safe_primary(briefing.get("primary")),
        "riskAlerts": risk_alerts,
        "portfolioState": _safe_portfolio_state(briefing.get("portfolioState")),
        "opinions": opinions,
        "portfolioChanges": changes,
        "evidence": [],
    }


def _source_card(source: str, source_url: str, generated_at: str) -> dict[str, Any]:
    return {
        "source": source[:120],
        "sourceUrl": source_url[:1000],
        "observedAt": generated_at or None,
        "methodologyVersion": _METHODOLOGY,
    }


def _tab(status: str, *, sources: list[dict[str, Any]] | None = None, metrics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"status": status, "sources": sources or [], "metrics": metrics or []}


def _availability(payload: Mapping[str, Any], *, has_content: bool) -> str:
    """Legacy payload status values such as ``system`` are not UI availability."""
    if has_content:
        return "AVAILABLE"
    raw = str(payload.get("status") or "").upper()
    return "UNAVAILABLE" if raw in {"", "UNAVAILABLE", "FAILED", "ERROR"} else "PARTIAL"


def _component(value: Any, *, generated_at: str, default_source: str) -> dict[str, Any]:
    raw = _mapping(value)
    source_codes = raw.get("sourceCodes") or raw.get("sourceCode") or []
    if isinstance(source_codes, str):
        source_codes = [source_codes]
    sources = [
        _source_card(str(code), str(raw.get("sourceUrl") or ""), generated_at)
        for code in source_codes
        if isinstance(code, str) and code.strip()
    ] or ([_source_card(default_source, str(raw.get("sourceUrl") or ""), generated_at)] if raw else [])
    result: dict[str, Any] = {
        "status": _availability(raw, has_content=bool(raw)),
        "sources": sources,
    }
    for key in ("latest", "summaries", "series"):
        if key in raw:
            result[key] = _mapping(raw[key]) if key == "latest" else _items(raw[key])
    return result


def build_imported_crypto_market_pulse(
    pulse_payload: Mapping[str, Any],
    calendar_payload: Mapping[str, Any],
    *,
    checksum: str,
    mode: str,
) -> dict[str, Any]:
    """Adapt imported crypto pulse data without claiming local observation evidence."""
    pulse = _mapping(pulse_payload)
    calendar = _mapping(calendar_payload)
    generated_at = str(pulse.get("generatedAt") or "")
    fear_raw = _mapping(pulse.get("fearGreed"))
    etf_raw = _mapping(pulse.get("etfFlows"))
    fund_raw = _mapping(pulse.get("fundFlows"))
    fear_source = _source_card(
        str(fear_raw.get("sourceCode") or "datavest-production-import"),
        str(fear_raw.get("sourceUrl") or ""),
        generated_at,
    )
    flow_sources = [
        _source_card(str(code), "", generated_at)
        for code in (etf_raw.get("sourceCodes") or [])
        if isinstance(code, str) and code.strip()
    ] or [_source_card("datavest-production-import", "", generated_at)]
    fear = {
        "status": _availability(
            fear_raw,
            has_content=bool(_mapping(fear_raw.get("latest")) or _items(fear_raw.get("series"))),
        ),
        "sources": [fear_source] if fear_raw else [],
        "latest": _mapping(fear_raw.get("latest")) or None,
        "series": _items(fear_raw.get("series")),
    }
    etf = {
        "status": _availability(
            etf_raw,
            has_content=bool(_items(etf_raw.get("summaries")) or _items(etf_raw.get("series"))),
        ),
        "sources": flow_sources if etf_raw else [],
        "series": _items(etf_raw.get("series")),
        "summaries": _items(etf_raw.get("summaries")),
    }
    fund = _component(fund_raw, generated_at=generated_at, default_source="datavest-production-import")
    margin = _component(pulse.get("marginBorrow"), generated_at=generated_at, default_source="datavest-production-import")
    liquidation = _component(pulse.get("liquidationMaxPain"), generated_at=generated_at, default_source="datavest-production-import")
    derivatives = {
        "status": "AVAILABLE" if margin["status"] == "AVAILABLE" or liquidation["status"] == "AVAILABLE" else "UNAVAILABLE",
        "marginBorrow": margin,
        "liquidationMaxPain": liquidation,
    }
    available = lambda value: _availability(_mapping(value), has_content=bool(_mapping(value)))
    overview_sources = [*fear.get("sources", []), *etf.get("sources", [])]
    overview_metrics = []
    if _mapping(fear.get("latest")):
        overview_metrics.append({"metric": "crypto.fear_greed.index", "value": fear["latest"].get("value"), "effectiveAt": fear["latest"].get("effectiveAt"), "source": fear_source["source"]})
    tabs = {
        "overview": {**_tab("AVAILABLE" if overview_sources else "UNAVAILABLE", sources=overview_sources, metrics=overview_metrics), "fearGreed": fear, "etfFlows": etf},
        "flows": {**_tab("AVAILABLE" if etf["status"] == "AVAILABLE" or fund["status"] == "AVAILABLE" else "UNAVAILABLE", sources=[*etf["sources"], *fund["sources"]], metrics=[*etf["summaries"], *fund.get("summaries", [])]), "etfFlows": etf, "fundFlows": fund},
        "sentimentDerivatives": {**_tab("AVAILABLE" if fear["status"] == "AVAILABLE" or derivatives["status"] == "AVAILABLE" else "UNAVAILABLE", sources=[*fear["sources"], *derivatives.get("sources", [])], metrics=overview_metrics), "fearGreed": fear, "derivatives": derivatives},
        "cycle": _tab(available(pulse.get("cycleIndicators"))),
        "onchain": _tab("UNAVAILABLE"),
        "whales": _tab(available(pulse.get("largeAddressActivity"))),
    }
    events = []
    for item in _items(calendar.get("events"))[:100]:
        event = str(item.get("event") or "").strip()
        effective_at = str(item.get("eventAt") or item.get("eventDate") or "").strip()
        if event and effective_at:
            events.append({"effectiveAt": effective_at, "event": event[:240], "impact": str(item.get("impact") or "unknown")[:80], "source": str(item.get("sourceCode") or "datavest-production-import")[:120]})
    return {
        "generatedAt": generated_at or None,
        "mode": mode,
        "status": "PARTIAL" if overview_sources or events else "UNAVAILABLE",
        "methodologyVersion": _METHODOLOGY,
        "evidenceChecksum": str(checksum or "") or None,
        "tabs": tabs,
        "calendar": {"status": "AVAILABLE" if events else "UNAVAILABLE", "events": events, "sources": [_source_card("datavest-production-import", "", generated_at)] if events else []},
    }


def _merge_missing(imported: Any, runtime: Any) -> Any:
    """Enrich an imported read model with persisted live observations.

    The production account export remains authoritative for fields it contains.
    Runtime observations only fill fields that the export did not carry, which
    lets the old account snapshot and the newly wired legacy collectors coexist
    without silently replacing imported values.
    """
    if isinstance(imported, Mapping) and isinstance(runtime, Mapping):
        merged = dict(imported)
        for key, value in runtime.items():
            if key not in merged or merged[key] in (None, "", [], {}):
                merged[key] = value
            elif isinstance(merged[key], Mapping) and isinstance(value, Mapping):
                merged[key] = _merge_missing(merged[key], value)
        return merged
    return imported if imported not in (None, "", [], {}) else runtime


def _merge_sources(imported: Any, runtime: Any) -> list[dict[str, Any]]:
    """Union source cards while preserving the order shown by the import."""
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in [*_items(imported), *_items(runtime)]:
        source = str(item.get("source") or "")
        source_url = str(item.get("sourceUrl") or "")
        key = (source, source_url)
        if source and key not in seen:
            seen.add(key)
            result.append(dict(item))
    return result


def merge_imported_crypto_market_pulse(
    imported: Mapping[str, Any], runtime: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge a user's legacy production snapshot with local LIVE observations.

    This is intentionally a read-model merge, not a data migration.  The
    immutable observation rows remain the source for any newly collected tab;
    the response records that lineage so callers can explain why a tab contains
    both imported and runtime data.
    """
    result = dict(imported)
    imported_tabs = _mapping(imported.get("tabs"))
    runtime_tabs = _mapping(runtime.get("tabs"))
    merged_tabs: dict[str, Any] = {}
    runtime_used: list[str] = []
    for key in ("overview", "flows", "sentimentDerivatives", "cycle", "onchain", "whales"):
        imported_tab = _mapping(imported_tabs.get(key))
        runtime_tab = _mapping(runtime_tabs.get(key))
        if not imported_tab:
            merged_tabs[key] = dict(runtime_tab)
            if runtime_tab.get("status") != "UNAVAILABLE":
                runtime_used.append(key)
            continue
        if not runtime_tab or runtime_tab.get("status") == "UNAVAILABLE":
            merged_tabs[key] = dict(imported_tab)
            continue
        merged = _merge_missing(imported_tab, runtime_tab)
        merged["sources"] = _merge_sources(imported_tab.get("sources"), runtime_tab.get("sources"))
        if imported_tab.get("status") == "UNAVAILABLE":
            merged["status"] = runtime_tab.get("status")
        if runtime_tab.get("status") != "UNAVAILABLE":
            runtime_used.append(key)
        merged["dataOrigin"] = "legacy-import+live-observations"
        merged_tabs[key] = merged
    result["tabs"] = merged_tabs

    imported_calendar = _mapping(imported.get("calendar"))
    runtime_calendar = _mapping(runtime.get("calendar"))
    imported_events = _items(imported_calendar.get("events"))
    runtime_events = _items(runtime_calendar.get("events"))
    events = [dict(item) for item in imported_events]
    event_keys = {
        (str(item.get("effectiveAt") or ""), str(item.get("event") or ""), str(item.get("source") or ""))
        for item in events
    }
    for item in runtime_events:
        key = (str(item.get("effectiveAt") or ""), str(item.get("event") or ""), str(item.get("source") or ""))
        if key not in event_keys:
            events.append(dict(item))
            event_keys.add(key)
    result["calendar"] = {
        **imported_calendar,
        "status": "AVAILABLE" if events else "UNAVAILABLE",
        "events": events[:100],
        "sources": _merge_sources(imported_calendar.get("sources"), runtime_calendar.get("sources")),
    }

    available_tabs = sum(
        1 for value in merged_tabs.values() if _mapping(value).get("status") == "AVAILABLE"
    )
    result["status"] = "AVAILABLE" if available_tabs == 7 else "PARTIAL" if available_tabs else "UNAVAILABLE"
    result["dataLineage"] = {
        "legacyImportChecksum": imported.get("evidenceChecksum"),
        "runtimeObservationMerge": bool(runtime_used),
        "runtimeTabs": runtime_used,
        "runtimeGeneratedAt": runtime.get("generatedAt"),
    }
    return result


__all__ = [
    "build_imported_crypto_market_pulse",
    "build_imported_overview",
    "merge_imported_crypto_market_pulse",
]
