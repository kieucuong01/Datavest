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
)
_ETF_ASSET_ORDER = ("BTC", "ETH", "SOL", "XRP", "HYPE", "DOGE", "LINK", "AVAX", "HBAR", "LTC", "BNB", "DOT", "SUI")
_ETF_SOURCE_ASSETS = {
    "btc": "BTC", "eth": "ETH", "sol": "SOL", "xrp": "XRP", "hyp": "HYPE",
    "doge": "DOGE", "link": "LINK", "avax": "AVAX", "hbar": "HBAR", "ltc": "LTC",
    "bnb": "BNB", "dot": "DOT", "sui": "SUI",
}
_ETF_SOURCES = {
    **{f"cryptoetf-{code}-etf": asset for code, asset in _ETF_SOURCE_ASSETS.items()},
    "xoomar-btc-etf": "BTC",
    "xoomar-eth-etf": "ETH",
    "farside-btc-etf": "BTC",
    "farside-eth-etf": "ETH",
    "farside-sol-etf": "SOL",
}
_ETF_SOURCE_PRIORITY = {
    **{f"cryptoetf-{code}-etf": 0 for code in _ETF_SOURCE_ASSETS},
    "xoomar-btc-etf": 1,
    "xoomar-eth-etf": 1,
    "farside-btc-etf": 2,
    "farside-eth-etf": 2,
    "farside-sol-etf": 2,
}
_WHALE_SOURCES = {"bitinfocharts-top-addresses", "mempool-btc-large-addresses"}
_RETIRED_SOURCES = frozenset({"cbbi-public"})
_RETIRED_METRIC_PREFIXES = ("crypto.cycle.cbbi.",)
_RETIRED_METRIC_PREFIXES_EXACT = frozenset({"crypto.onchain.rhodl_ratio"})
_ONCHAIN_GROUPS = (
    (
        "valuation",
        (
            "crypto.onchain.mvrv",
            "crypto.onchain.nupl",
            "crypto.onchain.supply_in_profit_pct",
            "crypto.onchain.sopr",
        ),
    ),
    (
        "holders",
        (
            "crypto.onchain.lth_supply",
            "crypto.onchain.sth_supply",
            "crypto.onchain.hodl_waves",
            "crypto.onchain.realized_price",
            "crypto.onchain.cost_basis",
        ),
    ),
    (
        "liquidity",
        (
            "crypto.onchain.exchange_",
            "crypto.stablecoin.",
            "crypto.defi.chain_tvl_usd",
        ),
    ),
    (
        "network",
        (
            "crypto.onchain.active_addresses",
            "crypto.onchain.transaction_count",
            "crypto.onchain.transfer_count",
            "crypto.onchain.total_fees_native",
            "crypto.mempool.",
            "crypto.mining.",
            "crypto.chain.block_height",
            "crypto.eth.burn",
            "crypto.eth.staking",
            "crypto.eth.validator_queue",
        ),
    ),
)


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


def _is_retired_row(row: Mapping[str, Any]) -> bool:
    source = str(row.get("source") or "").strip().lower()
    metric = _metric(row)
    return source in _RETIRED_SOURCES or metric.startswith(_RETIRED_METRIC_PREFIXES) or metric in _RETIRED_METRIC_PREFIXES_EXACT


def _onchain_group(metric: str) -> str | None:
    for key, patterns in _ONCHAIN_GROUPS:
        for pattern in patterns:
            if metric == pattern or metric.startswith(pattern):
                return key
    return None


def _effective(row: Mapping[str, Any]) -> str:
    return str(row.get("effectiveAt") or "")


def _effective_day(row: Mapping[str, Any]) -> str:
    value = _effective(row)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10]


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
            str(_dimensions(row).get("dimension") or ""),
            str(_dimensions(row).get("label") or ""),
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
    # Preserve distinct effective dates for charts while retaining the newest
    # observation when a provider republishes the same data point.
    grouped: dict[tuple[str, ...], Mapping[str, Any]] = {}
    for row in rows:
        if _number(row) is None or not _effective(row):
            continue
        dimensions = _dimensions(row)
        key = (
            str(row.get("source") or ""),
            _metric(row),
            str(row.get("symbol") or ""),
            str(dimensions.get("fund") or ""),
            str(dimensions.get("dimension") or ""),
            str(dimensions.get("label") or ""),
            str(dimensions.get("address") or ""),
            str(dimensions.get("rank") or ""),
            str(dimensions.get("entity_category") or ""),
            _effective(row),
        )
        current = grouped.get(key)
        if current is None or (_observed(row), str(row.get("id") or "")) > (
            _observed(current),
            str(current.get("id") or ""),
        ):
            grouped[key] = row
    values = list(grouped.values())
    values.sort(key=lambda item: _effective(item))
    result = []
    for row in values[-limit:]:
        point = {
            "effectiveAt": _effective(row),
            "value": _number(row),
            "metric": _metric(row),
            "symbol": row.get("symbol"),
            "source": row.get("source"),
        }
        dimensions = _dimensions(row)
        for dimension, output_key in (
            ("address", "address"),
            ("rank", "rank"),
            ("label", "label"),
            ("entity_category", "entityCategory"),
            ("label_status", "labelStatus"),
        ):
            value = dimensions.get(dimension)
            if value not in {None, ""}:
                point[output_key] = value
        result.append(point)
    return result


def _preferred_etf_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Choose one provider per asset/date, keeping the most authoritative flow."""
    selected: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        source = str(row.get("source") or "")
        asset = str(row.get("symbol") or _ETF_SOURCES.get(source, "")).upper()
        key = (asset, _effective_day(row))
        current = selected.get(key)
        if current is None:
            selected[key] = row
            continue
        current_source = str(current.get("source") or "")
        candidate_order = (-_ETF_SOURCE_PRIORITY.get(source, 99), _observed(row), str(row.get("id") or ""))
        current_order = (-_ETF_SOURCE_PRIORITY.get(current_source, 99), _observed(current), str(current.get("id") or ""))
        if candidate_order > current_order:
            selected[key] = row
    return list(selected.values())


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


def _onchain_tab(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Expose the product taxonomy without promoting unrelated market rows."""
    grouped_rows: dict[str, list[Mapping[str, Any]]] = {
        key: [] for key, _patterns in _ONCHAIN_GROUPS
    }
    for row in rows:
        group = _onchain_group(_metric(row))
        if group is not None:
            grouped_rows[group].append(row)

    all_rows = [row for group_rows in grouped_rows.values() for row in group_rows]
    groups = []
    for key, _patterns in _ONCHAIN_GROUPS:
        group_rows = grouped_rows[key]
        groups.append(
            {
                "key": key,
                "status": _status(group_rows),
                "sources": _sources(group_rows),
                "metrics": _metric_cards(group_rows),
                "series": _series(group_rows, limit=2_000),
            }
        )
    return {
        "status": _status(all_rows),
        "sources": _sources(all_rows),
        "metrics": _metric_cards(all_rows),
        "series": _series(all_rows, limit=4_000),
        "groups": groups,
    }


def _latest_point(rows: Iterable[Mapping[str, Any]], *, metric: str) -> dict[str, Any] | None:
    matches = [row for row in rows if _metric(row) == metric]
    points = _series(matches, limit=1)
    return points[-1] if points else None


def _latest_address_points(
    rows: Iterable[Mapping[str, Any]], *, metric: str
) -> list[dict[str, Any]]:
    """Return one latest point per address for the whale movers table."""
    matches = [
        row for row in rows
        if _metric(row) == metric and _dimensions(row).get("address")
    ]
    if not matches:
        return []
    latest_day = max(_effective_day(row) for row in matches)
    grouped: dict[str, Mapping[str, Any]] = {}
    for row in matches:
        if _effective_day(row) != latest_day:
            continue
        address = str(_dimensions(row).get("address") or "")
        current = grouped.get(address)
        if current is None or (_observed(row), str(row.get("id") or "")) > (
            _observed(current), str(current.get("id") or "")
        ):
            grouped[address] = row
    return _series(grouped.values(), limit=len(grouped))


def _whale_movers(
    whale_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    changes = _latest_address_points(
        whale_rows, metric="crypto.large_address.address_balance_change_btc"
    )
    balances = {
        str(point.get("address")): point
        for point in _latest_address_points(
            whale_rows, metric="crypto.large_address.address_balance_btc"
        )
        if point.get("address")
    }

    def enrich(point: Mapping[str, Any]) -> dict[str, Any]:
        address = str(point.get("address") or "")
        balance = balances.get(address)
        return {
            **dict(point),
            "balance": balance.get("value") if balance else None,
            "rank": point.get("rank") or (balance or {}).get("rank"),
            "label": point.get("label") or (balance or {}).get("label"),
            "entityCategory": point.get("entityCategory") or (balance or {}).get("entityCategory"),
        }

    accumulating = sorted(
        (enrich(point) for point in changes if point.get("value", 0) > 0),
        key=lambda point: float(point.get("value") or 0), reverse=True,
    )
    distributing = sorted(
        (enrich(point) for point in changes if point.get("value", 0) < 0),
        key=lambda point: float(point.get("value") or 0),
    )
    return {
        "effectiveAt": max((_effective_day(row) for row in whale_rows if _metric(row) == "crypto.large_address.address_balance_change_btc"), default=None),
        "accumulating": accumulating[:8],
        "distributing": distributing[:8],
    }


def _whale_flow_tab(
    whale_rows: list[Mapping[str, Any]],
    exchange_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build an explicitly heuristic whale-flow view from persisted evidence.

    Address-balance snapshots can only describe the tracked cohort.  They are
    deliberately paired with a broad exchange-netflow measure before exposing
    an accumulation/distribution label; a single source never becomes a trade
    signal.
    """
    combined = [*whale_rows, *exchange_rows]
    if not combined:
        return {
            "status": "UNAVAILABLE",
            "sources": [],
            "metrics": [],
            "series": [],
            "cohort": {},
            "exchangePressure": {},
            "quality": {},
            "insight": {"tone": "INSUFFICIENT", "confidence": "LOW", "reasonMetrics": []},
        }

    change = _latest_point(whale_rows, metric="crypto.large_address.balance_change_btc")
    matched_change = _latest_point(whale_rows, metric="crypto.large_address.matched_balance_change_btc")
    increase = _latest_point(whale_rows, metric="crypto.large_address.balance_increase_btc")
    decrease = _latest_point(whale_rows, metric="crypto.large_address.balance_decrease_btc")
    balance = _latest_point(whale_rows, metric="crypto.large_address.reviewed_non_exchange_balance_btc")
    tracked_balance = _latest_point(whale_rows, metric="crypto.large_address.tracked_balance_btc")
    netflow = _latest_point(exchange_rows, metric="crypto.onchain.exchange_netflow_native")
    reserve = _latest_point(exchange_rows, metric="crypto.onchain.exchange_reserve_native")
    coverage = _latest_point(whale_rows, metric="crypto.large_address.label_coverage")
    flow_coverage = _latest_point(whale_rows, metric="crypto.large_address.flow_coverage")
    tracked = _latest_point(whale_rows, metric="crypto.large_address.tracked_address_count")
    excluded = _latest_point(whale_rows, metric="crypto.large_address.excluded_address_count")
    accumulating_count = _latest_point(whale_rows, metric="crypto.large_address.accumulating_address_count")
    distributing_count = _latest_point(whale_rows, metric="crypto.large_address.distributing_address_count")
    top10_share = _latest_point(whale_rows, metric="crypto.large_address.top10_share")
    top25_share = _latest_point(whale_rows, metric="crypto.large_address.top25_share")
    detail_received = _latest_address_points(whale_rows, metric="crypto.large_address.address_received_total_btc")
    detail_sent = _latest_address_points(whale_rows, metric="crypto.large_address.address_sent_total_btc")

    # Negative exchange netflow means coins leave exchanges.  Only the two
    # independent, same-direction signals qualify for a directional label.
    aligned_signals = bool(change and netflow and _effective_day(change) == _effective_day(netflow))
    if aligned_signals and change["value"] > 0 and netflow["value"] < 0:
        tone = "ACCUMULATION"
    elif aligned_signals and change["value"] < 0 and netflow["value"] > 0:
        tone = "DISTRIBUTION"
    elif change or netflow:
        tone = "MIXED"
    else:
        tone = "INSUFFICIENT"

    coverage_value = coverage["value"] if coverage else None
    fresh_days = {
        _effective_day(point)
        for point in (change, balance, netflow, reserve)
        if point is not None
    }
    confidence = "MEDIUM" if tone in {"ACCUMULATION", "DISTRIBUTION"} and (coverage_value is None or coverage_value >= 0.5) and len(fresh_days) == 1 else "LOW"
    reason_metrics = [
        point["metric"]
        for point in (change, netflow)
        if point is not None
    ]

    return {
        "status": "AVAILABLE" if change and netflow else "PARTIAL",
        "sources": _sources(combined),
        "metrics": _metric_cards(combined),
        "series": _series(combined, limit=730),
        "cohort": {
            "latestBalance": balance,
            "latestTrackedBalance": tracked_balance,
            "latestChange": change,
            "latestMatchedChange": matched_change,
            "latestIncrease": increase,
            "latestDecrease": decrease,
            "latestTop10Share": top10_share,
            "latestTop25Share": top25_share,
        },
        "exchangePressure": {"latestNetflow": netflow, "latestReserve": reserve},
        "movers": _whale_movers(whale_rows),
        "detail": {
            "addressCount": len({str(point.get("address")) for point in [*detail_received, *detail_sent] if point.get("address")}),
            "scope": "top12_non_excluded" if detail_received or detail_sent else None,
        },
        "quality": {
            "labelCoverage": coverage_value,
            "trackedAddressCount": tracked["value"] if tracked else None,
            "excludedAddressCount": excluded["value"] if excluded else None,
            "flowCoverage": flow_coverage["value"] if flow_coverage else None,
            "matchedAddressCount": (
                _latest_point(whale_rows, metric="crypto.large_address.matched_address_count") or {}
            ).get("value"),
            "qualityTier": "heuristic",
        },
        "insight": {"tone": tone, "confidence": confidence, "reasonMetrics": reason_metrics},
    }


def build_crypto_market_pulse(rows: Iterable[Mapping[str, Any]], *, mode: str) -> dict[str, Any]:
    """Build the old page's tab model from immutable LIVE/DEMO observations."""
    normalized = [row for row in rows if isinstance(row, Mapping) and row.get("dataClass") == mode.upper()]
    crypto = [row for row in normalized if row.get("market") == "crypto" and not _is_retired_row(row)]
    calendar_rows = [row for row in normalized if row.get("source") == "cryptocraft"]

    fear_rows = [row for row in crypto if _metric(row) == "crypto.fear_greed.index"]
    # Alternative.me publishes daily history back to 2018. Keep it in the
    # read-model so the UI can offer the 7D/1M/3M/1Y/max ranges without
    # inventing or re-fetching chart points client-side.
    fear_points = _series(fear_rows, limit=4_000)
    fear_latest = fear_points[-1] if fear_points else None
    fear = {
        "status": _status(fear_rows),
        "source": _sources(fear_rows),
        "latest": fear_latest,
        "series": fear_points,
    }

    etf_rows = _preferred_etf_rows([
        row for row in crypto
        if row.get("source") in _ETF_SOURCES
        and _metric(row) == "crypto.etf.net_flow_usd"
        and str(_dimensions(row).get("fund") or "").upper() == "TOTAL"
    ])
    etf_points = _series(etf_rows, limit=180)
    summaries: list[dict[str, Any]] = []
    for asset in _ETF_ASSET_ORDER:
        candidates = [row for row in etf_rows if str(row.get("symbol") or _ETF_SOURCES.get(str(row.get("source")), "")) == asset]
        points = _series(candidates, limit=1)
        if points:
            summaries.append({"asset": asset, "latest": points[-1]["value"], "effectiveAt": points[-1]["effectiveAt"]})
    etf = {"status": _status(etf_rows), "sources": _sources(etf_rows), "series": etf_points, "summaries": summaries}

    fund_rows = [
        row for row in crypto
        if row.get("source") == "coinshares-weekly"
        and _metric(row) == "crypto.coinshares.net_flow_usd"
    ]
    fund_points = _series(fund_rows, limit=180)
    fund_summaries: list[dict[str, Any]] = []
    labels = sorted({str(_dimensions(row).get("label") or row.get("symbol") or "Total") for row in fund_rows})
    for label in labels:
        candidates = [
            row for row in fund_rows
            if str(_dimensions(row).get("label") or row.get("symbol") or "Total") == label
        ]
        points = _series(candidates, limit=1)
        if points:
            fund_summaries.append({"asset": label, "latest": points[-1]["value"], "effectiveAt": points[-1]["effectiveAt"]})
    fund = {"status": _status(fund_rows), "sources": _sources(fund_rows), "series": fund_points, "summaries": fund_summaries}

    derivative_rows = [
        row for row in crypto
        if str(row.get("source") or "") in {"openbb-deribit", "coinglass-margin-borrow", "coinglass-liquidation-maxpain"}
        or _metric(row).startswith("crypto.derivatives.")
    ]
    cycle_rows = [row for row in crypto if _metric(row).startswith("crypto.cycle.")]
    halving_rows = [row for row in crypto if _metric(row) == "crypto.chain.block_height"]
    btc_price_rows = [
        row for row in crypto
        if _metric(row) == "crypto.market.price_usd" and str(row.get("symbol") or "").upper() == "BTC"
    ]
    onchain_rows = [row for row in crypto if _onchain_group(_metric(row)) is not None]
    whale_rows = [row for row in crypto if row.get("source") in _WHALE_SOURCES or _metric(row).startswith("crypto.large_address.")]
    exchange_rows = [
        row for row in crypto
        if str(row.get("symbol") or "").upper() == "BTC"
        and _metric(row) in {
            "crypto.onchain.exchange_netflow_native",
            "crypto.onchain.exchange_reserve_native",
        }
    ]
    whale_flow = _whale_flow_tab(whale_rows, exchange_rows)
    def tab(rows_for_tab: list[Mapping[str, Any]], *, series_limit: int = 90) -> dict[str, Any]:
        if not rows_for_tab:
            return _unavailable()
        return {"status": "AVAILABLE", "sources": _sources(rows_for_tab), "metrics": _metric_cards(rows_for_tab), "series": _series(rows_for_tab, limit=series_limit)}

    events = []
    for row in sorted(calendar_rows, key=_effective)[:100]:
        dimensions = _dimensions(row)
        event = str(dimensions.get("event") or "")
        if not event:
            continue
        events.append({"effectiveAt": _effective(row), "event": event, "impact": str(dimensions.get("impact") or "unknown"), "source": "cryptocraft"})

    tabs = {
        "overview": {"status": "AVAILABLE" if crypto else "UNAVAILABLE", "sources": _sources(crypto), "metrics": _metric_cards(crypto), "fearGreed": fear, "etfFlows": etf, "fundFlows": fund},
        "flows": {
            "status": "AVAILABLE" if etf["status"] == "AVAILABLE" or fund["status"] == "AVAILABLE" or whale_flow["status"] in {"AVAILABLE", "PARTIAL"} else "UNAVAILABLE",
            "sources": [*etf["sources"], *fund["sources"], *whale_flow["sources"]],
            "metrics": _metric_cards([*etf_rows, *fund_rows, *whale_rows, *exchange_rows]),
            "etfFlows": etf,
            "fundFlows": fund,
            "whaleFlows": whale_flow,
        },
        "sentimentDerivatives": {**tab(derivative_rows + fear_rows, series_limit=10_000), "fearGreed": fear},
        "cycle": {
            **tab(cycle_rows, series_limit=100_000),
            "halving": tab(halving_rows, series_limit=100_000),
            "priceHistory": tab(btc_price_rows, series_limit=10_000),
        },
        "onchain": _onchain_tab(onchain_rows),
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
