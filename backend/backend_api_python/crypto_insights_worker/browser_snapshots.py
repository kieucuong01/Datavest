"""Collect public crypto insight pages into validated local snapshots."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import argparse
import asyncio
import ast
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from app.services.smart_insights.browser_snapshots import (
    SnapshotUnavailable,
    load_snapshot,
    snapshot_root,
    write_snapshot,
)


PayloadCollector = Callable[[str, datetime], Mapping[str, object]]
_BASE_DAILY_SOURCES = ("alternative-fng", "blockchaincenter-altcoin-season", "cbbi-public", "bitinfocharts-top-addresses")
CRYPTOETF_ASSETS = ("btc", "eth", "sol", "xrp", "hyp", "doge", "link", "avax", "hbar", "ltc", "bnb", "dot", "sui")
CRYPTOETF_SYMBOLS = {"hyp": "HYPE"}
CRYPTOETF_SOURCES = tuple(f"cryptoetf-{asset}-etf" for asset in CRYPTOETF_ASSETS)
XOOMAR_SOURCES = ("xoomar-btc-etf", "xoomar-eth-etf")
FARSIDE_SOURCES = ("farside-btc-etf", "farside-eth-etf", "farside-sol-etf")
COINSHARES_SOURCE = "coinshares-weekly"
SOURCE_URLS = {
    "alternative-fng": "https://api.alternative.me/fng/?limit=0&format=json",
    "farside-btc-etf": "https://farside.co.uk/btc/",
    "farside-eth-etf": "https://farside.co.uk/eth/",
    "farside-sol-etf": "https://farside.co.uk/sol/",
    **{f"cryptoetf-{asset}-etf": f"https://api.cryptoetf.today/api/v1/flows/{asset}" for asset in CRYPTOETF_ASSETS},
    "xoomar-btc-etf": "https://xoomar.com/api/markets/etf-flows?asset=btc&days=90",
    "xoomar-eth-etf": "https://xoomar.com/api/markets/etf-flows?asset=eth&days=90",
    "blockchaincenter-altcoin-season": "https://www.blockchaincenter.net/altcoin-season-index/",
    "cbbi-public": "https://colintalkscrypto.com/cbbi/data/latest.json",
    "coinshares-weekly": "https://coinshares.com/insights/research-data/",
    "bitinfocharts-top-addresses": "https://bitinfocharts.com/top-100-richest-bitcoin-addresses.html",
}

_CBBI_COMPONENTS = {
    "PiCycle": "pi_cycle",
    "RUPL": "rupl_nupl",
    "RHODL": "rhodl",
    "Puell": "puell",
    "2YMA": "two_year_ma",
    "Trolololo": "trolololo",
    "MVRV": "mvrv",
    "ReserveRisk": "reserve_risk",
    "Woobull": "woobull",
}
_COINSHARES_REPORT_DATE = re.compile(r"fund-flows-(\d{1,2})-(\d{1,2})-(\d{2}|\d{4})/?$", re.IGNORECASE)
_COINSHARES_TOTAL = re.compile(
    r"\b(inflows|outflows)\b[^.]{0,120}?\b(?:US\s*\$|\$)\s*(\d+(?:\.\d+)?)\s*(bn|billion|m|million)\b",
    re.IGNORECASE,
)
_BITINFO_ADDRESS = re.compile(r"^(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{20,80})$")
_BITINFO_BTC = re.compile(r"([\d,]+(?:\.\d+)?)\s*BTC\b", re.IGNORECASE)
_BITINFO_DETAIL_RECEIVED = re.compile(
    r"Received:\s*([\d,\s.]+)\s*BTC\s*\(([\d,\s]+)\s*ins\).*?\blast:\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE | re.DOTALL,
)
_BITINFO_DETAIL_SENT = re.compile(
    r"Sent:\s*([\d,\s.]+)\s*BTC\s*\(([\d,\s]+)\s*outs\).*?\blast:\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE | re.DOTALL,
)
_BITINFO_DETAIL_UTXO = re.compile(r"Unspent outputs:\s*([\d,\s]+)", re.IGNORECASE)
_BITINFO_EXCLUSIONS = {
    "exchange": ("binance", "coinbase", "bitfinex", "kraken", "okx", "huobi", "gemini", "bittrex", "upbit", "bybit"),
    "custodian": ("custodian", "custody", "xapo", "bitgo", "copper"),
    "miner": ("miner", "mining pool"),
    "government": ("government", "department of justice", "doj"),
    "special_entity": ("hack", "recovery", "mtgox", "mt. gox", "satoshi"),
}


def _number(value: object) -> str:
    try:
        parsed = Decimal(str(value).replace(",", "").replace("$", "").strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SnapshotUnavailable("INVALID_VALUE") from exc
    if not parsed.is_finite():
        raise SnapshotUnavailable("INVALID_VALUE")
    return str(parsed)


def _timestamp(value: object) -> str:
    try:
        return datetime.fromtimestamp(int(str(value)), timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise SnapshotUnavailable("INVALID_TIMESTAMP") from exc


def parse_fear_greed(body: object) -> list[dict[str, str]]:
    payload = _decode(body)
    rows = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list) or not rows:
        raise SnapshotUnavailable("REQUIRED_RECORDS")
    result = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise SnapshotUnavailable("INVALID_RECORD")
        result.append({
            "effective_at": _timestamp(row.get("timestamp")),
            "metric": "crypto.fear_greed.index",
            "value": _number(row.get("value")),
            "unit": "index",
            "classification": str(row.get("value_classification") or "").strip(),
        })
    return sorted(result, key=lambda row: row["effective_at"])


def parse_farside(asset: str, table: Sequence[Sequence[object]]) -> list[dict[str, str]]:
    if len(table) < 2:
        raise SnapshotUnavailable("SCHEMA_DRIFT")
    header = {str(name).strip().casefold(): index for index, name in enumerate(table[0])}
    if "date" not in header or "total" not in header:
        raise SnapshotUnavailable("SCHEMA_DRIFT")
    result = []
    for cells in table[1:]:
        if len(cells) <= max(header["date"], header["total"]):
            raise SnapshotUnavailable("SCHEMA_DRIFT")
        raw_date = str(cells[header["date"]]).strip().rstrip("*")
        effective_at = None
        for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
            try:
                effective_at = datetime.strptime(raw_date, fmt).replace(tzinfo=timezone.utc).isoformat()
                break
            except ValueError:
                continue
        if effective_at is None:
            raise SnapshotUnavailable("INVALID_TIMESTAMP")
        total = _number(str(cells[header["total"]]).replace("(", "-").replace(")", ""))
        result.append({
            "effective_at": effective_at,
            "metric": "crypto.etf.net_flow_usd",
            "value": str(Decimal(total) * Decimal("1000000")),
            "unit": "USD",
            "asset": asset.upper(),
            "fund": "TOTAL",
        })
    if not result:
        raise SnapshotUnavailable("REQUIRED_RECORDS")
    return sorted(result, key=lambda row: row["effective_at"])


def _api_effective_at(value: object) -> str:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
    except (TypeError, ValueError) as exc:
        raise SnapshotUnavailable("INVALID_TIMESTAMP") from exc


def _etf_record(asset: str, date: object, value: object) -> dict[str, str]:
    return {
        "effective_at": _api_effective_at(date),
        "metric": "crypto.etf.net_flow_usd",
        "value": str(Decimal(_number(value)) * Decimal("1000000")),
        "unit": "USD",
        "asset": asset.upper(),
        "fund": "TOTAL",
    }


def parse_cryptoetf(asset: str, payload: object) -> list[dict[str, str]]:
    body = _decode(payload)
    days = body.get("days") if isinstance(body, Mapping) else None
    if not isinstance(days, list) or not days:
        raise SnapshotUnavailable("REQUIRED_RECORDS")
    records = []
    for day in days:
        if not isinstance(day, Mapping) or day.get("date") is None or day.get("netFlowUsdM") is None:
            raise SnapshotUnavailable("SCHEMA_DRIFT")
        records.append(_etf_record(asset, day.get("date"), day.get("netFlowUsdM")))
    return sorted(records, key=lambda row: row["effective_at"])


def parse_xoomar(asset: str, payload: object) -> list[dict[str, str]]:
    body = _decode(payload)
    rows = body.get("data") if isinstance(body, Mapping) else None
    if not isinstance(rows, list) or not rows:
        raise SnapshotUnavailable("REQUIRED_RECORDS")
    totals: dict[str, Decimal] = {}
    for row in rows:
        if not isinstance(row, Mapping) or row.get("date") is None:
            raise SnapshotUnavailable("SCHEMA_DRIFT")
        raw_flow = row.get("flowUsd")
        if raw_flow is None:
            continue
        date = _api_effective_at(row.get("date"))
        totals[date] = totals.get(date, Decimal("0")) + Decimal(_number(raw_flow))
    if not totals:
        raise SnapshotUnavailable("REQUIRED_RECORDS")
    return [
        {
            "effective_at": date,
            "metric": "crypto.etf.net_flow_usd",
            "value": format(value, "f"),
            "unit": "USD",
            "asset": asset.upper(),
            "fund": "TOTAL",
        }
        for date, value in sorted(totals.items())
    ]


_ALTCOIN_SEASON_METRICS = {
    "30": ("crypto.cycle.altcoin_season.month_index", "month"),
    "90": ("crypto.cycle.altcoin_season.index", "season_90d"),
    "365": ("crypto.cycle.altcoin_season.year_index", "year"),
}
_ALTCOIN_SEASON_STAT_FIELDS = (
    "days_since_last_alt", "days_since_last_btc",
    "avg_gap_alt_to_alt", "avg_gap_btc_to_btc",
    "longest_no_alt_streak", "longest_no_btc_streak",
    "avg_alt_run", "avg_btc_run", "max_alt_run", "max_btc_run",
    "altseasondays", "bitcoinseasondays",
)


def _embedded_object(text: str, key: str) -> Mapping[str, object] | None:
    """Read one structured object embedded in BlockchainCenter's Next payload."""
    decoded = text.replace('\\"', '"')
    marker = f'"{key}":'
    marker_index = decoded.find(marker)
    if marker_index < 0:
        return None
    start = decoded.find("{", marker_index + len(marker))
    if start < 0:
        return None
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(decoded)):
        character = decoded[index]
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                try:
                    payload = json.loads(decoded[start:index + 1])
                except json.JSONDecodeError:
                    return None
                return payload if isinstance(payload, Mapping) else None
    return None


def parse_altcoin_season(text: str) -> list[dict[str, str]]:
    score = _embedded_object(text, "score")
    stats = _embedded_object(text, "stats")
    records: list[dict[str, str]] = []
    latest_date = ""
    if isinstance(score, Mapping):
        for horizon, (metric, label) in _ALTCOIN_SEASON_METRICS.items():
            values_by_date = score.get(horizon)
            if not isinstance(values_by_date, Mapping):
                continue
            for raw_date, raw_value in values_by_date.items():
                try:
                    effective_at = datetime.fromisoformat(str(raw_date)).replace(tzinfo=timezone.utc).isoformat()
                except ValueError:
                    continue
                records.append({"effective_at": effective_at, "metric": metric, "value": _number(raw_value), "unit": "index", "horizon": label})
                if horizon == "90" and effective_at > latest_date:
                    latest_date = effective_at
    if not records:
        values = dict(re.findall(r"\b(Altcoin Season|Month|Year)\s*\(\s*(\d{1,3})\s*\)", text, flags=re.IGNORECASE))
        expected = {"Altcoin Season", "Month", "Year"}
        if set(values) != expected:
            raise SnapshotUnavailable("SCHEMA_DRIFT")
        return [
            {"metric": "crypto.cycle.altcoin_season.index", "value": values["Altcoin Season"], "unit": "index", "horizon": "season_90d"},
            {"metric": "crypto.cycle.altcoin_season.month_index", "value": values["Month"], "unit": "index", "horizon": "month"},
            {"metric": "crypto.cycle.altcoin_season.year_index", "value": values["Year"], "unit": "index", "horizon": "year"},
        ]
    stats_90 = stats.get("90") if isinstance(stats, Mapping) else None
    if isinstance(stats_90, Mapping) and latest_date:
        for field in _ALTCOIN_SEASON_STAT_FIELDS:
            if stats_90.get(field) is not None:
                records.append({"effective_at": latest_date, "metric": f"crypto.cycle.altcoin_season.stat.{field}", "value": _number(stats_90[field]), "unit": "days", "horizon": "season_90d"})
    return sorted(records, key=lambda row: (row["effective_at"], row["metric"]))


def parse_cbbi(payload: Mapping[str, object]) -> list[dict[str, str]]:
    confidence = payload.get("Confidence")
    if not isinstance(confidence, Mapping) or not confidence:
        raise SnapshotUnavailable("REQUIRED_RECORDS")
    result = []
    for raw_timestamp, value in confidence.items():
        effective_at = _timestamp(raw_timestamp)
        result.append({"effective_at": effective_at, "metric": "crypto.cycle.cbbi.confidence", "value": _number(value), "unit": "index"})
        for field, component in _CBBI_COMPONENTS.items():
            series = payload.get(field)
            if isinstance(series, Mapping) and raw_timestamp in series:
                component_value = series[raw_timestamp]
                if component_value is not None:
                    result.append({"effective_at": effective_at, "metric": f"crypto.cycle.cbbi.component.{component}", "value": _number(component_value), "unit": "index"})
    return sorted(result, key=lambda row: (row["effective_at"], row["metric"]))


def parse_coinshares_report(text: str, report_url: str) -> list[dict[str, str]]:
    date_match = _COINSHARES_REPORT_DATE.search(report_url.rstrip("/"))
    amount_match = _COINSHARES_TOTAL.search(text)
    if date_match is None or amount_match is None:
        raise SnapshotUnavailable("SCHEMA_DRIFT")
    year = int(date_match.group(3))
    if year < 100:
        year += 2000
    try:
        effective_at = datetime(year, int(date_match.group(2)), int(date_match.group(1)), tzinfo=timezone.utc)
    except ValueError as exc:
        raise SnapshotUnavailable("INVALID_TIMESTAMP") from exc
    multiplier = Decimal("1000000000") if amount_match.group(3).casefold() in {"bn", "billion"} else Decimal("1000000")
    amount = Decimal(amount_match.group(2)) * multiplier
    if amount_match.group(1).casefold() == "outflows":
        amount = -amount
    value = format(amount, "f").rstrip("0").rstrip(".")
    return [{
        "effective_at": effective_at.isoformat(),
        "metric": "crypto.coinshares.net_flow_usd",
        "value": value or "0",
        "unit": "USD",
        "dimension": "total",
        "label": "Total",
    }]


def _bitinfo_decimal(value: object) -> Decimal:
    match = _BITINFO_BTC.search(str(value))
    if match is None:
        raise SnapshotUnavailable("INVALID_VALUE")
    try:
        result = Decimal(match.group(1).replace(",", ""))
    except InvalidOperation as exc:
        raise SnapshotUnavailable("INVALID_VALUE") from exc
    if not result.is_finite() or result < 0:
        raise SnapshotUnavailable("INVALID_VALUE")
    return result


def _bitinfo_detail_decimal(value: object) -> Decimal:
    try:
        result = Decimal(re.sub(r"[\s,]", "", str(value)))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SnapshotUnavailable("INVALID_VALUE") from exc
    if not result.is_finite() or result < 0:
        raise SnapshotUnavailable("INVALID_VALUE")
    return result


def _bitinfo_category(label: str | None) -> str | None:
    if not label:
        return None
    normalized = label.casefold()
    for category, patterns in _BITINFO_EXCLUSIONS.items():
        if any(pattern in normalized for pattern in patterns):
            return category
    return "reviewed_other"


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def parse_bitinfocharts_detail(text: str) -> dict[str, object]:
    """Normalize lifetime counters from one public BitInfoCharts address page.

    These counters are context only. They are not treated as daily flow because
    the page reports lifetime totals rather than a dated transaction ledger.
    """
    received = _BITINFO_DETAIL_RECEIVED.search(text)
    sent = _BITINFO_DETAIL_SENT.search(text)
    utxo = _BITINFO_DETAIL_UTXO.search(text)
    if received is None or sent is None or utxo is None:
        raise SnapshotUnavailable("SCHEMA_DRIFT")
    try:
        received_count = int(re.sub(r"[\s,]", "", received.group(2)))
        sent_count = int(re.sub(r"[\s,]", "", sent.group(2)))
        unspent_outputs = int(re.sub(r"[\s,]", "", utxo.group(1)))
        last_activity = max(
            datetime.fromisoformat(received.group(3)).date(),
            datetime.fromisoformat(sent.group(3)).date(),
        )
    except ValueError as exc:
        raise SnapshotUnavailable("SCHEMA_DRIFT") from exc
    if min(received_count, sent_count, unspent_outputs) < 0:
        raise SnapshotUnavailable("INVALID_VALUE")
    return {
        "received_total": _bitinfo_detail_decimal(received.group(1)),
        "sent_total": _bitinfo_detail_decimal(sent.group(1)),
        "received_count": received_count,
        "sent_count": sent_count,
        "unspent_outputs": unspent_outputs,
        "last_activity": last_activity,
    }


def parse_bitinfocharts_rich_list(
    rows: Sequence[Mapping[str, object]],
    *,
    as_of: datetime,
    previous_balances: Mapping[str, object] | None = None,
) -> list[dict[str, str]]:
    """Normalize one Browser Use Rich List render into a bounded BTC cohort."""
    parsed: list[dict[str, object]] = []
    ranks: set[int] = set()
    addresses: set[str] = set()
    for row in rows:
        try:
            rank = int(str(row.get("rank") or ""))
        except (TypeError, ValueError) as exc:
            raise SnapshotUnavailable("SCHEMA_DRIFT") from exc
        address = str(row.get("address") or "").strip()
        if not 1 <= rank <= 100 or rank in ranks or not _BITINFO_ADDRESS.fullmatch(address) or address in addresses:
            raise SnapshotUnavailable("SCHEMA_DRIFT")
        balance = _bitinfo_decimal(row.get("balance"))
        if balance < Decimal("1000"):
            raise SnapshotUnavailable("SCHEMA_DRIFT")
        label = str(row.get("label") or "").strip() or None
        category = _bitinfo_category(label)
        parsed.append({"rank": rank, "address": address, "balance": balance, "label": label, "category": category, "excluded": category in _BITINFO_EXCLUSIONS})
        ranks.add(rank)
        addresses.add(address)
    if ranks != set(range(1, 101)):
        raise SnapshotUnavailable("SCHEMA_DRIFT")

    parsed.sort(key=lambda row: int(row["rank"]))
    labelled = [row for row in parsed if row["label"] is not None]
    excluded = [row for row in parsed if row["excluded"] is True]
    retained = [row for row in parsed if row["excluded"] is False]
    cohort_version = hashlib.sha256(json.dumps([
        {"address": row["address"], "balance": _decimal_text(row["balance"]), "category": row["category"], "rank": row["rank"]}
        for row in parsed
    ], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    effective_at = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    dimensions = {
        "cohort": "reviewed_non_exchange",
        "cohort_version": cohort_version,
        "label_coverage": _decimal_text(Decimal(len(labelled)) / Decimal(len(parsed))),
        "quality_tier": "heuristic",
    }

    records: list[dict[str, str]] = []
    def append(metric: str, value: Decimal, unit: str, **extra: str) -> None:
        records.append({"effective_at": effective_at, "metric": metric, "value": _decimal_text(value), "unit": unit, "symbol": "BTC", **dimensions, **extra, "warnings": ["HEURISTIC_ADDRESS_COHORT"]})

    append("crypto.large_address.tracked_balance_btc", sum((row["balance"] for row in parsed), Decimal("0")), "BTC")
    append("crypto.large_address.reviewed_non_exchange_balance_btc", sum((row["balance"] for row in retained), Decimal("0")), "BTC")
    append("crypto.large_address.excluded_balance_btc", sum((row["balance"] for row in excluded), Decimal("0")), "BTC")
    append("crypto.large_address.labelled_balance_btc", sum((row["balance"] for row in labelled), Decimal("0")), "BTC")
    append("crypto.large_address.tracked_address_count", Decimal(len(parsed)), "addresses")
    append("crypto.large_address.excluded_address_count", Decimal(len(excluded)), "addresses")
    append("crypto.large_address.labelled_address_count", Decimal(len(labelled)), "addresses")
    append("crypto.large_address.label_coverage", Decimal(len(labelled)) / Decimal(len(parsed)), "ratio")
    current = {str(row["address"]): row["balance"] for row in retained}
    for row in retained:
        address = str(row["address"])
        append(
            "crypto.large_address.address_balance_btc", row["balance"], "BTC",
            address=address, rank=str(row["rank"]),
            label_status="labelled" if row["label"] is not None else "unknown",
            entity_category=str(row["category"] or "unknown"),
            label=str(row["label"] or ""),
        )
    if previous_balances is not None:
        previous: dict[str, Decimal] = {}
        for address, raw_value in previous_balances.items():
            try:
                value = Decimal(str(raw_value))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise SnapshotUnavailable("INVALID_PREVIOUS_SNAPSHOT") from exc
            if not value.is_finite() or value < 0:
                raise SnapshotUnavailable("INVALID_PREVIOUS_SNAPSHOT")
            previous[str(address)] = value
        deltas: list[tuple[dict[str, object], Decimal]] = []
        for row in retained:
            address = str(row["address"])
            if address not in previous:
                continue
            delta = row["balance"] - previous[address]
            deltas.append((row, delta))
            append(
                "crypto.large_address.address_balance_change_btc", delta, "BTC",
                address=address, rank=str(row["rank"]),
                label_status="labelled" if row["label"] is not None else "unknown",
                entity_category=str(row["category"] or "unknown"),
                label=str(row["label"] or ""),
            )
        matched_change = sum((delta for _row, delta in deltas), Decimal("0"))
        increase = sum((delta for _row, delta in deltas if delta > 0), Decimal("0"))
        decrease = sum((delta for _row, delta in deltas if delta < 0), Decimal("0"))
        current_addresses = set(current)
        previous_addresses = set(previous)
        union_count = len(current_addresses | previous_addresses)
        append("crypto.large_address.balance_change_btc", sum(current.values(), Decimal("0")) - sum(previous.values(), Decimal("0")), "BTC")
        append("crypto.large_address.matched_balance_change_btc", matched_change, "BTC")
        append("crypto.large_address.balance_increase_btc", increase, "BTC")
        append("crypto.large_address.balance_decrease_btc", decrease, "BTC")
        append("crypto.large_address.accumulating_address_count", Decimal(sum(1 for _row, delta in deltas if delta > 0)), "addresses")
        append("crypto.large_address.distributing_address_count", Decimal(sum(1 for _row, delta in deltas if delta < 0)), "addresses")
        append("crypto.large_address.matched_address_count", Decimal(len(deltas)), "addresses")
        append("crypto.large_address.new_address_count", Decimal(len(current_addresses - previous_addresses)), "addresses")
        append("crypto.large_address.dropped_address_count", Decimal(len(previous_addresses - current_addresses)), "addresses")
        append("crypto.large_address.flow_coverage", Decimal(len(deltas)) / Decimal(union_count or 1), "ratio")

    retained_total = sum((row["balance"] for row in retained), Decimal("0"))
    for threshold, metric in ((10, "crypto.large_address.top10_share"), (25, "crypto.large_address.top25_share")):
        top_balance = sum((row["balance"] for row in retained if int(row["rank"]) <= threshold), Decimal("0"))
        append(metric, top_balance / retained_total if retained_total else Decimal("0"), "ratio")

    category_balances: dict[str, Decimal] = {}
    for row in retained:
        category = str(row["category"] or "unknown")
        category_balances[category] = category_balances.get(category, Decimal("0")) + row["balance"]
    for category, value in sorted(category_balances.items()):
        append("crypto.large_address.category_balance_btc", value, "BTC", entity_category=category)
    return records


def _payload(source_code: str, records: list[dict[str, str]], *, as_of: datetime) -> dict[str, object]:
    if source_code == "blockchaincenter-altcoin-season":
        effective_at = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        records = [{**record, "effective_at": record.get("effective_at") or effective_at} for record in records]
    ordered = sorted(records, key=lambda row: row["effective_at"])
    return {
        "source": source_code, "source_url": SOURCE_URLS[source_code], "schema_version": 1,
        "fetched_at": as_of.astimezone(timezone.utc).isoformat(),
        "coverage": {"record_count": len(ordered), "oldest_effective_at": ordered[0]["effective_at"], "newest_effective_at": ordered[-1]["effective_at"]},
        "records": ordered,
    }


def _decode(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value


def _browser_site_packages() -> None:
    configured = os.getenv("CRYPTO_INSIGHTS_BROWSER_USE_SITE_PACKAGES", "").strip()
    candidate = configured or str(Path(os.getenv("LOCALAPPDATA", "")) / "QuantDinger" / "browser-use-0.13.8")
    if candidate and Path(candidate).is_dir() and candidate not in sys.path:
            sys.path.insert(0, candidate)


def prepare_browser_profile(path: Path) -> Path:
    """Reuse public-data profile storage without retaining dead Chromium locks."""
    resolved = path.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        (resolved / name).unlink(missing_ok=True)
    return resolved


def create_browser_session():
    _browser_site_packages()
    from browser_use import BrowserSession
    remote_cdp_url = os.getenv("CRYPTO_INSIGHTS_BROWSER_CDP_URL", "").strip()
    if remote_cdp_url:
        # BitInfoCharts' Cloudflare challenge rejects container headless
        # Chromium.  Connect Browser Use to a dedicated, local headed Chrome
        # profile instead; the sidecar still owns parsing and atomic snapshots.
        return BrowserSession(
            cdp_url=remote_cdp_url,
            keep_alive=True,
            allowed_domains=[
                "api.alternative.me", "farside.co.uk", "www.farside.co.uk",
                "www.blockchaincenter.net", "blockchaincenter.net", "colintalkscrypto.com",
                "coinshares.com", "www.coinshares.com", "bitinfocharts.com", "www.bitinfocharts.com",
            ],
        )
    options = {
        "headless": os.getenv("CRYPTO_INSIGHTS_BROWSER_HEADLESS", "true").lower() in {"1", "true", "yes"},
        "keep_alive": False,
        "enable_default_extensions": False,
        "allowed_domains": [
            "api.alternative.me", "farside.co.uk", "www.farside.co.uk",
            "www.blockchaincenter.net", "blockchaincenter.net", "colintalkscrypto.com",
            "coinshares.com", "www.coinshares.com",
            "bitinfocharts.com", "www.bitinfocharts.com",
        ],
        "args": ["--disable-dev-shm-usage", "--disable-gpu"],
        "user_data_dir": str(prepare_browser_profile(Path(os.getenv("CRYPTO_INSIGHTS_BROWSER_USER_DATA_DIR", "data/browser-profiles/crypto-insights")))),
    }
    executable = os.getenv("CRYPTO_INSIGHTS_BROWSER_EXECUTABLE_PATH", "").strip()
    if executable:
        options["executable_path"] = executable
    return BrowserSession(**options)


async def _page_text(page: Any, url: str) -> object:
    await page.goto(url)
    await asyncio.sleep(max(1, float(os.getenv("CRYPTO_INSIGHTS_BROWSER_PAGE_WAIT_SECONDS", "3"))))
    return _decode(await page.evaluate("() => document.body.innerText || ''"))


async def _page_html(page: Any, url: str) -> str:
    await page.goto(url)
    await asyncio.sleep(max(1, float(os.getenv("CRYPTO_INSIGHTS_BROWSER_PAGE_WAIT_SECONDS", "3"))))
    content = await page.evaluate("() => document.documentElement.outerHTML || ''")
    return str(content)


def _api_json(url: str, *, api_key: str | None = None) -> object:
    headers = {"Accept": "application/json", "User-Agent": "DataVest Smart Insights/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with urlopen(Request(url, headers=headers), timeout=20) as response:
            return _decode(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise SnapshotUnavailable("API_UNAVAILABLE") from exc


def scheduled_daily_sources() -> tuple[str, ...]:
    provider_sources = CRYPTOETF_SOURCES if os.getenv("CRYPTOETF_API_KEY", "").strip() else (*XOOMAR_SOURCES, "farside-sol-etf")
    return (*_BASE_DAILY_SOURCES, *provider_sources)


async def _farside_table(page: Any, url: str) -> list[list[str]]:
    await page.goto(url)
    await asyncio.sleep(max(1, float(os.getenv("CRYPTO_INSIGHTS_BROWSER_PAGE_WAIT_SECONDS", "3"))))
    tables = _decode(await page.evaluate("""() => Array.from(document.querySelectorAll('table')).map(table => Array.from(table.querySelectorAll('tr')).map(row => Array.from(row.querySelectorAll('th,td')).map(cell => (cell.innerText || '').trim())))"""))
    if not isinstance(tables, list):
        raise SnapshotUnavailable("SCHEMA_DRIFT")
    matches = [table for table in tables if table and isinstance(table[0], list) and {'date', 'total'} <= {str(value).casefold() for value in table[0]}]
    if len(matches) != 1:
        raise SnapshotUnavailable("SCHEMA_DRIFT")
    return matches[0]


async def _bitinfocharts_rows(page: Any, url: str) -> list[dict[str, str]]:
    """Read only the public rich-list table after Browser Use finishes rendering."""
    await page.goto(url)
    # Cloudflare's managed challenge is normally solved by the real browser
    # before the site table appears. Poll instead of treating its first page as
    # an empty rich list.
    deadline = asyncio.get_running_loop().time() + max(12, float(os.getenv("CRYPTO_INSIGHTS_BITINFO_WAIT_SECONDS", "30")))
    while True:
        extracted = _decode(await page.evaluate(r"""() => {
          const clean = value => (value || '').replace(/\s+/g, ' ').trim();
          const addressPattern = /(?:bc1[a-z0-9]{20,80}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})/i;
          for (const table of document.querySelectorAll('table')) {
            const header = Array.from(table.querySelectorAll('tr')).find(row => row.querySelectorAll('th,td').length >= 3);
            if (!header) continue;
            const headings = Array.from(header.querySelectorAll('th,td')).map(cell => clean(cell.innerText).toLowerCase());
            const addressIndex = headings.findIndex(value => value === 'address' || value.includes('address'));
            const balanceIndex = headings.findIndex(value => value === 'balance' || value.includes('balance'));
            if (addressIndex < 0 || balanceIndex < 0) continue;
            const rows = Array.from(table.querySelectorAll('tr')).slice(Array.from(table.querySelectorAll('tr')).indexOf(header) + 1)
              .map(row => Array.from(row.querySelectorAll('th,td')))
              .filter(cells => cells.length > Math.max(addressIndex, balanceIndex))
              .map(cells => {
                const addressText = clean(cells[addressIndex].innerText);
                const address = (addressText.match(addressPattern) || [''])[0];
                const rank = (clean(cells[0].innerText).match(/\d+/) || [''])[0];
                const label = clean(addressText.replace(address, ''))
                  .replace(/^wallet:\s*/i, '').replace(/\bbalance:\s*$/i, '').trim();
                return {rank, address, balance: clean(cells[balanceIndex].innerText), label};
              })
              .filter(row => row.rank && row.address && /BTC\b/i.test(row.balance));
            if (rows.length >= 100) return rows.slice(0, 100);
          }
          return [];
        }"""))
        if isinstance(extracted, list) and len(extracted) >= 100 and all(isinstance(row, Mapping) for row in extracted):
            return [{str(key): str(value) for key, value in row.items()} for row in extracted]
        if asyncio.get_running_loop().time() >= deadline:
            raise SnapshotUnavailable("CLOUDFLARE_OR_SCHEMA_DRIFT")
        await asyncio.sleep(2)


async def _bitinfocharts_detail_text(page: Any, address: str) -> str:
    """Read one address page through the same headed Browser Use session."""
    url = f"https://bitinfocharts.com/bitcoin/address/{address}"
    await page.goto(url)
    deadline = asyncio.get_running_loop().time() + max(
        8, float(os.getenv("CRYPTO_INSIGHTS_BITINFO_DETAIL_WAIT_SECONDS", "15"))
    )
    while True:
        text = str(await page.evaluate("() => document.body.innerText || ''"))
        lowered = text.casefold()
        if all(marker in lowered for marker in ("received:", "sent:", "unspent outputs:")):
            return text
        if asyncio.get_running_loop().time() >= deadline:
            raise SnapshotUnavailable("CLOUDFLARE_OR_SCHEMA_DRIFT")
        await asyncio.sleep(2)


async def _bitinfocharts_detail_records(
    page: Any,
    rows: Sequence[Mapping[str, object]],
    *,
    as_of: datetime,
) -> list[dict[str, object]]:
    """Best-effort lifetime context for the largest reviewed addresses.

    BitInfoCharts can challenge individual address pages independently. A
    detail failure must not discard the validated top-100 balance snapshot, so
    each page is isolated and the list remains the source of truth for daily
    flow metrics.
    """
    try:
        limit = max(0, min(25, int(os.getenv("CRYPTO_INSIGHTS_BITINFO_DETAIL_LIMIT", "12"))))
    except ValueError:
        limit = 12
    if limit == 0:
        return []
    candidates = [
        row for row in rows
        if _bitinfo_category(str(row.get("label") or "").strip() or None) not in _BITINFO_EXCLUSIONS
    ][:limit]
    effective_at = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    result: list[dict[str, object]] = []
    for row in candidates:
        address = str(row.get("address") or "").strip()
        if not _BITINFO_ADDRESS.fullmatch(address):
            continue
        try:
            detail = parse_bitinfocharts_detail(await _bitinfocharts_detail_text(page, address))
        except Exception:
            continue
        dimensions = {
            "cohort": "reviewed_non_exchange",
            "quality_tier": "heuristic",
            "address": address,
            "rank": str(row.get("rank") or ""),
            "label_status": "labelled" if str(row.get("label") or "").strip() else "unknown",
            "entity_category": str(_bitinfo_category(str(row.get("label") or "").strip() or None) or "unknown"),
            "detail_scope": "top12_non_excluded",
            "last_activity_at": detail["last_activity"].isoformat(),
        }
        for metric, value, unit in (
            ("crypto.large_address.address_received_total_btc", detail["received_total"], "BTC"),
            ("crypto.large_address.address_sent_total_btc", detail["sent_total"], "BTC"),
            ("crypto.large_address.address_received_count", Decimal(detail["received_count"]), "transactions"),
            ("crypto.large_address.address_sent_count", Decimal(detail["sent_count"]), "transactions"),
            ("crypto.large_address.address_unspent_output_count", Decimal(detail["unspent_outputs"]), "outputs"),
                ("crypto.large_address.address_last_activity_age_days", Decimal(max(0, (as_of.astimezone(timezone.utc).date() - detail["last_activity"]).days)), "days"),
        ):
            result.append({
                "effective_at": effective_at,
                "metric": metric,
                "value": _decimal_text(value),
                "unit": unit,
                "symbol": "BTC",
                **dimensions,
                "warnings": ["HEURISTIC_ADDRESS_COHORT", "ADDRESS_LIFETIME_TOTALS"],
            })
    return result


def _bitinfo_previous_balances(as_of: datetime) -> Mapping[str, object] | None:
    try:
        payload = load_snapshot("bitinfocharts-top-addresses", now=as_of)
    except SnapshotUnavailable:
        return None
    records = payload.get("records")
    if not isinstance(records, list):
        return None
    balances = {
        str(record.get("address")): record.get("value")
        for record in records
        if isinstance(record, Mapping)
        and record.get("metric") == "crypto.large_address.address_balance_btc"
        and str(record.get("address") or "").strip()
    }
    return balances or None


async def collect_source(source_code: str, page: Any | None, *, as_of: datetime) -> Mapping[str, object]:
    if source_code not in SOURCE_URLS:
        raise SnapshotUnavailable("UNKNOWN_SOURCE")
    if source_code.startswith("cryptoetf-"):
        api_key = os.getenv("CRYPTOETF_API_KEY", "").strip()
        if not api_key:
            raise SnapshotUnavailable("API_KEY_REQUIRED")
        asset = source_code.split("-")[1]
        records = parse_cryptoetf(CRYPTOETF_SYMBOLS.get(asset, asset.upper()), _api_json(SOURCE_URLS[source_code], api_key=api_key))
    elif source_code.startswith("xoomar-"):
        records = parse_xoomar(source_code.split("-")[1].upper(), _api_json(SOURCE_URLS[source_code]))
    elif source_code == "alternative-fng":
        # This is a documented free JSON endpoint; no browser session is
        # needed, and limit=0 supplies the one-time complete history.
        records = parse_fear_greed(_api_json(SOURCE_URLS[source_code]))
    elif page is None:
        raise SnapshotUnavailable("BROWSER_REQUIRED")
    elif source_code.startswith("farside-"):
        asset = source_code.split("-")[1].upper()
        records = parse_farside(asset, await _farside_table(page, SOURCE_URLS[source_code]))
    elif source_code == "bitinfocharts-top-addresses":
        rendered_rows = await _bitinfocharts_rows(page, SOURCE_URLS[source_code])
        records = parse_bitinfocharts_rich_list(
            rendered_rows,
            as_of=as_of,
            previous_balances=_bitinfo_previous_balances(as_of),
        )
        records.extend(await _bitinfocharts_detail_records(page, rendered_rows, as_of=as_of))
    elif source_code == "blockchaincenter-altcoin-season":
        records = parse_altcoin_season(await _page_html(page, SOURCE_URLS[source_code]))
    elif source_code == "cbbi-public":
        body = await _page_text(page, SOURCE_URLS[source_code])
        if not isinstance(body, Mapping):
            raise SnapshotUnavailable("INVALID_RESPONSE")
        records = parse_cbbi(body)
    else:
        index_url = SOURCE_URLS[source_code]
        await page.goto(index_url)
        await asyncio.sleep(max(1, float(os.getenv("CRYPTO_INSIGHTS_BROWSER_PAGE_WAIT_SECONDS", "3"))))
        links = _decode(await page.evaluate("""() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href).filter(href => /fund-flows-\\d{1,2}-\\d{1,2}-\\d{2,4}\\/?$/i.test(href))"""))
        if not isinstance(links, list) or not links:
            raise SnapshotUnavailable("SCHEMA_DRIFT")
        records = []
        for report_url in dict.fromkeys(str(link) for link in links):
            records.extend(parse_coinshares_report(str(await _page_text(page, report_url)), report_url))
    return _payload(source_code, records, as_of=as_of)


async def browser_backfill(source_codes: Sequence[str]) -> dict[str, dict[str, object]]:
    session = None
    page = None
    try:
        now = datetime.now(timezone.utc)
        result: dict[str, dict[str, object]] = {}
        for source_code in source_codes:
            try:
                if source_code not in {*CRYPTOETF_SOURCES, *XOOMAR_SOURCES, "alternative-fng"} and page is None:
                    session = create_browser_session()
                    await session.start()
                    page = await session.get_current_page()
                payload = await collect_source(source_code, page, as_of=now)
                write_snapshot(source_code, payload)
                result[source_code] = {"status": "ok", **_coverage(payload)}
            except SnapshotUnavailable as exc:
                result[source_code] = {"status": "failed", "error": str(exc)}
            except Exception as exc:
                result[source_code] = {"status": "failed", "error": f"UNEXPECTED:{type(exc).__name__}"}
        return result
    finally:
        if session is not None:
            # A CDP session belongs to the dedicated local Chrome process, not
            # the sidecar. Disconnect without killing that visible browser.
            if os.getenv("CRYPTO_INSIGHTS_BROWSER_CDP_URL", "").strip():
                await session.stop()
            else:
                await session.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Browser Use crypto insight snapshots")
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--sources", default=",")
    args = parser.parse_args()
    source_codes = tuple(item.strip() for item in args.sources.split(",") if item.strip()) or (*scheduled_daily_sources(), COINSHARES_SOURCE)
    if args.backfill:
        result = asyncio.run(browser_backfill(source_codes))
        print(json.dumps(result, ensure_ascii=False))
        if any(value["status"] != "ok" for value in result.values()):
            raise SystemExit(1)
        return
    async def loop() -> None:
        seen: set[str] = set()
        zone = ZoneInfo("Asia/Ho_Chi_Minh")
        while True:
            local_now = datetime.now(zone)
            due = scheduled_daily_sources() if (local_now.hour, local_now.minute) == (8, 15) else ((COINSHARES_SOURCE,) if local_now.weekday() in {0, 1} and (local_now.hour, local_now.minute) == (18, 0) else ())
            key = f"{local_now.date().isoformat()}-{local_now.hour:02d}-{local_now.minute:02d}"
            if due and key not in seen:
                print(json.dumps(await browser_backfill(due), ensure_ascii=False))
                seen.add(key)
            await asyncio.sleep(30)
    asyncio.run(loop())


def _coverage(payload: Mapping[str, object]) -> dict[str, object]:
    coverage = payload.get("coverage")
    if not isinstance(coverage, Mapping):
        raise SnapshotUnavailable("INVALID_COVERAGE")
    return {
        "recordCount": coverage.get("record_count"),
        "oldestEffectiveAt": coverage.get("oldest_effective_at"),
        "newestEffectiveAt": coverage.get("newest_effective_at"),
    }


def backfill(
    source_codes: Sequence[str],
    *,
    collect: PayloadCollector,
    root: Path | None = None,
    as_of: datetime | None = None,
) -> dict[str, dict[str, object]]:
    """Publish sources independently so one failure cannot replace another source."""
    observed_at = as_of or datetime.now(timezone.utc)
    target_root = root or snapshot_root()
    result: dict[str, dict[str, object]] = {}
    for source_code in source_codes:
        try:
            payload = collect(source_code, observed_at)
            write_snapshot(source_code, payload, root=target_root)
            result[source_code] = {"status": "ok", **_coverage(payload)}
        except SnapshotUnavailable as exc:
            result[source_code] = {"status": "failed", "error": str(exc)}
        except Exception as exc:
            result[source_code] = {"status": "failed", "error": f"UNEXPECTED:{type(exc).__name__}"}
    return result


__all__ = ["backfill"]


if __name__ == "__main__":
    main()
