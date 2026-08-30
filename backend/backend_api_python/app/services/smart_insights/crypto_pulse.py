"""Read model for the legacy DataVest Crypto Market Pulse.

The pulse is deliberately assembled only from persisted observations.  This
keeps the UI reproducible: every displayed number still has a source URL,
timestamp, methodology version and checksum in the evidence drawer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


_TAB_KEYS = (
    "overview",
    "flows",
    "sentimentDerivatives",
    "cycle",
    "onchain",
    "whales",
)
_ETF_SOURCES = {"farside-btc-etf": "BTC", "farside-eth-etf": "ETH", "farside-sol-etf": "SOL"}
_ONCHAIN_SOURCES = {"defillama-stablecoins", "defillama-chains", "mempool-space", "coinmetrics-community"}
_WHALE_SOURCES = {"bitinfocharts-top-addresses", "mempool-btc-large-addresses"}


def _value(row: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = row.get("value")
    return raw if isinstance(raw, Mapping) else {}


def _dimensions(row: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = _value(row).get("dimensions")
    return raw if isinstance(raw, Mapping) else {}


def _number(row: Mapping[str, Any]) -> float | None:
    try:
        value = float(_value(row).get("value"))
    except (TypeError, ValueError):
        return None
    return value if value == value and value not in (float("inf"), float("-inf")) else None


def _metric(row: Mapping[str, Any]) -> str:
    return str(_value(row).get("metric") or "")


def _effective(row: Mapping[str, Any]) -> str:
    return str(row.get("effectiveAt") or "")


def _observed(row: Mapping[str, Any]) -> str:
    return str(row.get("observedAt") or "")


def _source_card(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": str(row.get("source") or ""),
        "sourceUrl": str(row.get("sourceUrl") or ""),
        "observedAt": _observed(row) or None,
        "methodologyVersion": str(row.get("methodologyVersion") or ""),
    }


def _unavailable() -> dict[str, Any]:
    return {"status": "UNAVAILABLE", "sources": [], "metrics": []}


def _status(rows: Iterable[Mapping[str, Any]]) -> str:
    return "AVAILABLE" if any(True for _ in rows) else "UNAVAILABLE"


def _latest(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    grouped: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("source") or ""),
            _metric(row),
            str(row.get("symbol") or ""),
            str(_dimensions(row).get("fund") or ""),
        )
        current = grouped.get(key)
        if current is None or (_effective(row), _observed(row), str(row.get("id") or "")) > (
            _effective(current),
            _observed(current),
            str(current.get("id") or ""),
        ):
            grouped[key] = row
    return list(grouped.values())


def _series(rows: Iterable[Mapping[str, Any]], *, limit: int = 90) -> list[dict[str, Any]]:
    values = [row for row in _latest(rows) if _number(row) is not None and _effective(row)]
    values.sort(key=lambda item: _effective(item))
    return [
        {
            "effectiveAt": _effective(row),
            "value": _number(row),
            "metric": _metric(row),
            "symbol": row.get("symbol"),
            "source": row.get("source"),
        }
        for row in values[-limit:]
    ]


def _metric_cards(rows: Iterable[Mapping[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for row in sorted(_latest(rows), key=lambda item: (_effective(item), _observed(item)), reverse=True):
        value = _number(row)
        if value is None:
            continue
        cards.append(
            {
                "metric": _metric(row),
                "value": value,
                "unit": _value(row).get("unit"),
                "symbol": row.get("symbol"),
                "effectiveAt": _effective(row),
                "source": row.get("source"),
                "evidenceId": row.get("id"),
            }
        )
        if len(cards) >= limit:
            break
    return cards


def _sources(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        source = str(row.get("source") or "")
        if source and (source not in latest or _observed(row) > _observed(latest[source])):
            latest[source] = row
    return [_source_card(row) for _, row in sorted(latest.items())]


def build_crypto_market_pulse(rows: Iterable[Mapping[str, Any]], *, mode: str) -> dict[str, Any]:
    """Build the old page's tab model from immutable LIVE/DEMO observations."""
    normalized = [row for row in rows if isinstance(row, Mapping) and row.get("dataClass") == mode.upper()]
    crypto = [row for row in normalized if row.get("market") == "crypto"]
    calendar_rows = [row for row in normalized if row.get("source") == "cryptocraft"]

    fear_rows = [row for row in crypto if _metric(row) == "crypto.fear_greed.index"]
    fear_points = _series(fear_rows, limit=30)
    fear_latest = fear_points[-1] if fear_points else None
    fear = {
        "status": _status(fear_rows),
        "source": _sources(fear_rows),
        "latest": fear_latest,
        "series": fear_points,
    }

    etf_rows = [
        row for row in crypto
        if row.get("source") in _ETF_SOURCES
        and _metric(row) == "crypto.etf.net_flow_usd"
        and str(_dimensions(row).get("fund") or "").upper() == "TOTAL"
    ]
    etf_points = _series(etf_rows, limit=180)
    summaries: list[dict[str, Any]] = []
    for asset in ("BTC", "ETH", "SOL"):
        candidates = [row for row in etf_rows if str(row.get("symbol") or _ETF_SOURCES.get(str(row.get("source")), "")) == asset]
        points = _series(candidates, limit=1)
        if points:
            summaries.append({"asset": asset, "latest": points[-1]["value"], "effectiveAt": points[-1]["effectiveAt"]})
    etf = {"status": _status(etf_rows), "sources": _sources(etf_rows), "series": etf_points, "summaries": summaries}

    derivative_rows = [
        row for row in crypto
        if str(row.get("source") or "") in {"openbb-deribit", "coinglass-margin-borrow", "coinglass-liquidation-maxpain"}
        or _metric(row).startswith("crypto.derivatives.")
    ]
    cycle_rows = [row for row in crypto if _metric(row).startswith("crypto.cycle.")]
    onchain_rows = [row for row in crypto if row.get("source") in _ONCHAIN_SOURCES or _metric(row).startswith("crypto.onchain.")]
    whale_rows = [row for row in crypto if row.get("source") in _WHALE_SOURCES or _metric(row).startswith("crypto.large_address.")]
    cbbi_rows = [row for row in cycle_rows if _metric(row).startswith("crypto.cycle.cbbi.")]

    def tab(rows_for_tab: list[Mapping[str, Any]]) -> dict[str, Any]:
        if not rows_for_tab:
            return _unavailable()
        return {"status": "AVAILABLE", "sources": _sources(rows_for_tab), "metrics": _metric_cards(rows_for_tab), "series": _series(rows_for_tab)}

    events = []
    for row in sorted(calendar_rows, key=_effective)[:100]:
        dimensions = _dimensions(row)
        event = str(dimensions.get("event") or "")
        if not event:
            continue
        events.append({"effectiveAt": _effective(row), "event": event, "impact": str(dimensions.get("impact") or "unknown"), "source": "cryptocraft"})

    tabs = {
        "overview": {"status": "AVAILABLE" if crypto else "UNAVAILABLE", "sources": _sources(crypto), "metrics": _metric_cards(crypto), "fearGreed": fear, "etfFlows": etf},
        "flows": {"status": etf["status"], "sources": etf["sources"], "metrics": _metric_cards(etf_rows), "etfFlows": etf},
        "sentimentDerivatives": {**tab(derivative_rows + fear_rows), "fearGreed": fear},
        "cycle": {**tab(cycle_rows), "cbbi": tab(cbbi_rows)},
        "onchain": tab(onchain_rows),
        "whales": tab(whale_rows),
    }
    available_tabs = sum(1 for value in tabs.values() if value["status"] == "AVAILABLE")
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": mode.lower(),
        "status": "AVAILABLE" if available_tabs == len(_TAB_KEYS) else "PARTIAL" if available_tabs else "UNAVAILABLE",
        "tabs": tabs,
        "calendar": {"status": "AVAILABLE" if events else "UNAVAILABLE", "events": events, "sources": _sources(calendar_rows)},
    }


__all__ = ["build_crypto_market_pulse"]
