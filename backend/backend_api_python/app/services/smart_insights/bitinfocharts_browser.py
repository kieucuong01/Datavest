"""Rendered BitInfoCharts collector ported from DataVest's old worker."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .collectors import CollectorUnavailable
from .contracts import Observation
from .legacy_browser import BrowserDocument, NodriverBrowserClient, observation
from .sources import source_for_code


_ADDRESS = re.compile(r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{20,80})\b")
_BALANCE = re.compile(r"([\d,]+(?:\.\d+)?)\s*BTC\b", re.IGNORECASE)
_LABEL = re.compile(r"wallet:\s*(.*?)\s*Balance:", re.IGNORECASE)
_REQUIRED_HEADERS = ("Address", "Balance", "First In", "Last In")
_CHALLENGE_MARKERS = ("cf-chl", "challenge-platform", "just a moment", "verify you are human")
_MAX_DETAIL_ADDRESSES = 12
_DETAIL_RECEIVED = re.compile(r"Received:\s*([\d,\s.]+)\s*BTC\s*\(([\d,\s]+)\s*ins\).*?\blast:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE | re.DOTALL)
_DETAIL_SENT = re.compile(r"Sent:\s*([\d,\s.]+)\s*BTC\s*\(([\d,\s]+)\s*outs\).*?\blast:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE | re.DOTALL)
_DETAIL_UTXO = re.compile(r"Unspent outputs:\s*([\d,\s]+)", re.IGNORECASE)
_EXCLUSION_PATTERNS = {
    "exchange": ("binance", "coinbase", "bitfinex", "kraken", "okx", "huobi", "gemini", "bittrex", "upbit", "bybit"),
    "custodian": ("custodian", "custody", "xapo", "bitgo", "copper"),
    "miner": ("miner", "mining pool"),
    "government": ("government", "department of justice", "doj"),
    "special_entity": ("hack", "recovery", "mtgox", "mt. gox", "satoshi"),
}


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _ready(html: str) -> bool:
    lowered = html.casefold()
    return (
        "/bitcoin/address/" in lowered
        and all(header.casefold() in lowered for header in _REQUIRED_HEADERS)
        and not any(marker in lowered for marker in _CHALLENGE_MARKERS)
    )


def _detail_ready(html: str) -> bool:
    lowered = html.casefold()
    return (
        all(marker in lowered for marker in ("balance:", "received:", "sent:", "unspent outputs:"))
        and not any(marker in lowered for marker in _CHALLENGE_MARKERS)
    )


def _btc(value: str) -> Decimal:
    match = _BALANCE.search(value)
    if match is None:
        raise CollectorUnavailable("INVALID_VALUE")
    try:
        result = Decimal(match.group(1).replace(",", ""))
    except InvalidOperation as exc:
        raise CollectorUnavailable("INVALID_VALUE") from exc
    if not result.is_finite() or result < 0:
        raise CollectorUnavailable("INVALID_VALUE")
    return result


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(re.sub(r"[\s,]", "", value))
    except InvalidOperation as exc:
        raise CollectorUnavailable("INVALID_VALUE") from exc
    if not result.is_finite() or result < 0:
        raise CollectorUnavailable("INVALID_VALUE")
    return result


def _parse_detail(html: str) -> dict[str, object]:
    received = _DETAIL_RECEIVED.search(html)
    sent = _DETAIL_SENT.search(html)
    utxo = _DETAIL_UTXO.search(html)
    if received is None or sent is None or utxo is None:
        raise CollectorUnavailable("SCHEMA_DRIFT")
    try:
        received_count = int(re.sub(r"[\s,]", "", received.group(2)))
        sent_count = int(re.sub(r"[\s,]", "", sent.group(2)))
        unspent_outputs = int(re.sub(r"[\s,]", "", utxo.group(1)))
        last_activity = max(
            datetime.fromisoformat(received.group(3)).date(),
            datetime.fromisoformat(sent.group(3)).date(),
        )
    except ValueError as exc:
        raise CollectorUnavailable("SCHEMA_DRIFT") from exc
    if min(received_count, sent_count, unspent_outputs) < 0:
        raise CollectorUnavailable("INVALID_VALUE")
    return {
        "received_total": _decimal(received.group(1)),
        "sent_total": _decimal(sent.group(1)),
        "received_count": received_count,
        "sent_count": sent_count,
        "unspent_outputs": unspent_outputs,
        "last_activity": last_activity,
    }


def _category(label: str | None) -> str | None:
    if label is None:
        return None
    normalized = label.casefold()
    for category, patterns in _EXCLUSION_PATTERNS.items():
        if any(pattern in normalized for pattern in patterns):
            return category
    return "reviewed_other"


def _parse_rows(html: str, *, source_url: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    tables = tuple(soup.find_all("table"))
    primary: list[tuple[object, dict[str, int]]] = []
    for table in tables:
        first = table.find("tr")
        cells = first.find_all(("td", "th"), recursive=False) if first else []
        headers = tuple(_text(cell.get_text(" ", strip=True)) for cell in cells)
        if all(required in headers for required in _REQUIRED_HEADERS):
            primary.append((table, {header: index for index, header in enumerate(headers)}))
    if len(primary) != 1:
        raise CollectorUnavailable("SCHEMA_DRIFT")
    table, columns = primary[0]
    rows: dict[int, list[object]] = {}
    for row in table.find_all("tr"):
        cells = row.find_all(("td", "th"), recursive=False)
        if len(cells) <= max(columns.values()):
            continue
        try:
            rank = int(_text(cells[0].get_text(" ", strip=True)))
        except ValueError:
            continue
        if not 1 <= rank <= 100:
            continue
        if rank in rows:
            raise CollectorUnavailable("DUPLICATE_SERIES")
        rows[rank] = cells
    if set(rows) != set(range(1, 101)):
        raise CollectorUnavailable("SCHEMA_DRIFT")

    parsed: list[dict[str, object]] = []
    addresses: set[str] = set()
    for rank in range(1, 101):
        cells = rows[rank]
        address_cell = cells[columns["Address"]]
        links = tuple(address_cell.select('a[href*="/bitcoin/address/"]'))
        if len(links) != 1:
            raise CollectorUnavailable("SCHEMA_DRIFT")
        href = links[0].get("href")
        if not isinstance(href, str):
            raise CollectorUnavailable("SCHEMA_DRIFT")
        resolved = urlsplit(urljoin(source_url, href))
        expected = urlsplit(source_url)
        prefix = "/bitcoin/address/"
        if (
            resolved.scheme != "https"
            or resolved.netloc != expected.netloc
            or resolved.username
            or resolved.password
            or not resolved.path.startswith(prefix)
            or resolved.query
            or resolved.fragment
        ):
            raise CollectorUnavailable("SCHEMA_DRIFT")
        address = resolved.path[len(prefix):]
        address_match = _ADDRESS.fullmatch(address)
        if address_match is None or address in addresses:
            raise CollectorUnavailable("INVALID_ADDRESS")
        addresses.add(address)
        cell_text = _text(address_cell.get_text(" ", strip=True))
        link_text = _text(links[0].get_text(" ", strip=True))
        suffix = cell_text[len(link_text):].strip() if cell_text.startswith(link_text) else cell_text
        label_match = _LABEL.search(f"{address} {suffix}")
        label = label_match.group(1).strip() if label_match else None
        balance = _btc(cells[columns["Balance"]].get_text(" ", strip=True))
        if balance < Decimal("1000"):
            continue
        category = _category(label)
        parsed.append({
            "rank": rank,
            "address": address,
            "balance": balance,
            "label": label,
            "category": category,
            "excluded": category in _EXCLUSION_PATTERNS,
        })
    if not parsed:
        raise CollectorUnavailable("SCHEMA_DRIFT")
    return parsed


class BitInfoChartsBrowserCollector:
    source_code = "bitinfocharts-top-addresses"

    def __init__(self, *, browser: NodriverBrowserClient | None = None) -> None:
        self.source = source_for_code(self.source_code)
        self.browser = browser or NodriverBrowserClient()

    def collect(
        self,
        as_of: datetime,
        *,
        previous_balances: Mapping[str, Decimal] | None = None,
    ) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        document = self.browser.fetch(self.source, self.source.urls[0], ready=_ready)
        parsed = _parse_rows(document.html, source_url=document.final_url)
        effective_at = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        current = {str(row["address"]): row["balance"] for row in parsed if row["excluded"] is False}
        labelled = [row for row in parsed if row["label"] is not None]
        excluded = [row for row in parsed if row["excluded"] is True]
        cohort_version = hashlib.sha256(json.dumps([
            {
                "address": row["address"],
                "balance": format(row["balance"], "f"),
                "category": row["category"],
                "excluded": row["excluded"],
                "label": row["label"],
                "rank": row["rank"],
            }
            for row in parsed
        ], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        dimensions = {
            "cohort": "reviewed_non_exchange",
            "cohort_version": cohort_version,
            "label_coverage": format((Decimal(len(labelled)) / Decimal(len(parsed))).quantize(Decimal("0.000001")), "f"),
            "quality_tier": "heuristic",
        }
        warning = ("HEURISTIC_ADDRESS_COHORT",)
        rows: list[Observation] = []
        for metric, value, unit in (
            ("crypto.large_address.tracked_balance_btc", sum((row["balance"] for row in parsed), Decimal("0")), "BTC"),
            ("crypto.large_address.reviewed_non_exchange_balance_btc", sum(current.values(), Decimal("0")), "BTC"),
            ("crypto.large_address.excluded_balance_btc", sum((row["balance"] for row in excluded), Decimal("0")), "BTC"),
            ("crypto.large_address.labelled_balance_btc", sum((row["balance"] for row in labelled), Decimal("0")), "BTC"),
            ("crypto.large_address.tracked_address_count", Decimal(len(parsed)), "addresses"),
            ("crypto.large_address.excluded_address_count", Decimal(len(excluded)), "addresses"),
            ("crypto.large_address.labelled_address_count", Decimal(len(labelled)), "addresses"),
            ("crypto.large_address.label_coverage", Decimal(len(labelled)) / Decimal(len(parsed)), "ratio"),
        ):
            rows.append(observation(source=self.source, document=document, metric=metric, value=value, unit=unit, effective_at=effective_at, symbol="BTC", dimensions=dimensions, warnings=warning))
        for row in parsed:
            if row["excluded"] is True:
                continue
            rows.append(observation(source=self.source, document=document, metric="crypto.large_address.address_balance_btc", value=row["balance"], unit="BTC", effective_at=effective_at, symbol="BTC", dimensions={**dimensions, "address": str(row["address"]), "rank": str(row["rank"]), "label_status": "labelled" if row["label"] is not None else "unknown", "entity_category": str(row["category"] or "unknown"), "label": str(row["label"] or "")}, warnings=warning))
        retained_total = sum((row["balance"] for row in parsed if row["excluded"] is False), Decimal("0"))
        for threshold, metric in ((10, "crypto.large_address.top10_share"), (25, "crypto.large_address.top25_share")):
            top_balance = sum((row["balance"] for row in parsed if row["excluded"] is False and int(row["rank"]) <= threshold), Decimal("0"))
            rows.append(observation(source=self.source, document=document, metric=metric, value=top_balance / retained_total if retained_total else Decimal("0"), unit="ratio", effective_at=effective_at, symbol="BTC", dimensions=dimensions, warnings=warning))
        category_balances: dict[str, Decimal] = {}
        for row in parsed:
            if row["excluded"] is False:
                category = str(row["category"] or "unknown")
                category_balances[category] = category_balances.get(category, Decimal("0")) + row["balance"]
        for category, value in sorted(category_balances.items()):
            rows.append(observation(source=self.source, document=document, metric="crypto.large_address.category_balance_btc", value=value, unit="BTC", effective_at=effective_at, symbol="BTC", dimensions={**dimensions, "entity_category": category}, warnings=warning))
        detail_candidates = [row for row in parsed if row["excluded"] is False][:_MAX_DETAIL_ADDRESSES]
        detail_documents = self._fetch_detail_documents(document, detail_candidates)
        for row, detail_document in zip(detail_candidates, detail_documents, strict=True):
            detail = _parse_detail(detail_document.html)
            activity_age_days = max(0, (effective_at.date() - detail["last_activity"]).days)
            detail_dimensions = {
                **dimensions,
                "address": str(row["address"]),
                "rank": str(row["rank"]),
                "label_status": "labelled" if row["label"] is not None else "unknown",
                "entity_category": str(row["category"] or "unknown"),
                "detail_scope": "top12_non_excluded",
                "last_activity_at": detail["last_activity"].isoformat(),
            }
            for metric, value, unit in (
                ("crypto.large_address.address_received_total_btc", detail["received_total"], "BTC"),
                ("crypto.large_address.address_sent_total_btc", detail["sent_total"], "BTC"),
                ("crypto.large_address.address_received_count", Decimal(detail["received_count"]), "transactions"),
                ("crypto.large_address.address_sent_count", Decimal(detail["sent_count"]), "transactions"),
                ("crypto.large_address.address_unspent_output_count", Decimal(detail["unspent_outputs"]), "outputs"),
                ("crypto.large_address.address_last_activity_age_days", Decimal(activity_age_days), "days"),
            ):
                rows.append(observation(source=self.source, document=detail_document, metric=metric, value=value, unit=unit, effective_at=effective_at, symbol="BTC", dimensions=detail_dimensions, warnings=(*warning, "ADDRESS_LIFETIME_TOTALS")))
        if previous_balances is not None:
            if any(value < 0 or not value.is_finite() for value in previous_balances.values()):
                raise CollectorUnavailable("INVALID_PREVIOUS_SNAPSHOT")
            deltas: list[tuple[dict[str, object], Decimal]] = []
            for row in parsed:
                if row["excluded"] is True or str(row["address"]) not in previous_balances:
                    continue
                address = str(row["address"])
                delta = row["balance"] - previous_balances[address]
                deltas.append((row, delta))
                rows.append(observation(source=self.source, document=document, metric="crypto.large_address.address_balance_change_btc", value=delta, unit="BTC", effective_at=effective_at, symbol="BTC", dimensions={**dimensions, "address": address, "rank": str(row["rank"]), "label_status": "labelled" if row["label"] is not None else "unknown", "entity_category": str(row["category"] or "unknown"), "label": str(row["label"] or "")}, warnings=warning))
            current_addresses = set(current)
            previous_addresses = set(previous_balances)
            union_count = len(current_addresses | previous_addresses)
            rows.extend((
                observation(source=self.source, document=document, metric=metric, value=value, unit=unit, effective_at=effective_at, symbol="BTC", dimensions=dimensions, warnings=warning)
                for metric, value, unit in (
                    ("crypto.large_address.balance_change_btc", sum(current.values(), Decimal("0")) - sum(previous_balances.values(), Decimal("0")), "BTC"),
                    ("crypto.large_address.matched_balance_change_btc", sum((delta for _row, delta in deltas), Decimal("0")), "BTC"),
                    ("crypto.large_address.balance_increase_btc", sum((delta for _row, delta in deltas if delta > 0), Decimal("0")), "BTC"),
                    ("crypto.large_address.balance_decrease_btc", sum((delta for _row, delta in deltas if delta < 0), Decimal("0")), "BTC"),
                    ("crypto.large_address.accumulating_address_count", Decimal(sum(1 for _row, delta in deltas if delta > 0)), "addresses"),
                    ("crypto.large_address.distributing_address_count", Decimal(sum(1 for _row, delta in deltas if delta < 0)), "addresses"),
                    ("crypto.large_address.matched_address_count", Decimal(len(deltas)), "addresses"),
                    ("crypto.large_address.new_address_count", Decimal(len(current_addresses - previous_addresses)), "addresses"),
                    ("crypto.large_address.dropped_address_count", Decimal(len(previous_addresses - current_addresses)), "addresses"),
                    ("crypto.large_address.flow_coverage", Decimal(len(deltas)) / Decimal(union_count or 1), "ratio"),
                )
            ))
        return tuple(rows)

    def _fetch_detail_documents(self, document: BrowserDocument, rows: list[dict[str, object]]) -> tuple[BrowserDocument, ...]:
        urls = tuple(urljoin(document.final_url, f"/bitcoin/address/{row['address']}") for row in rows)
        fetch_many = getattr(self.browser, "fetch_many", None)
        if callable(fetch_many):
            return tuple(fetch_many(self.source, urls, ready=_detail_ready))
        return tuple(self.browser.fetch(self.source, url, ready=_detail_ready) for url in urls)


__all__ = ["BitInfoChartsBrowserCollector"]
