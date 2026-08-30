"""Farside ETF total-flow collector using a bounded standard-library table parser."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport, Transport


_SOURCE_BY_ASSET = {"BTC": "farside-btc-etf", "ETH": "farside-eth-etf", "SOL": "farside-sol-etf"}
_DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%b %d, %Y")


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _date(value: str) -> datetime:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip().rstrip("*"), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise CollectorUnavailable("INVALID_TIMESTAMP")


def _millions(value: str) -> Decimal:
    cleaned = value.replace(",", "").replace("$", "").strip().rstrip("*")
    if cleaned in {"", "-", "—", "–", "n/a", "N/A"}:
        return Decimal("0")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1].strip()
    try:
        parsed = Decimal(cleaned) * Decimal("1000000")
    except InvalidOperation as exc:
        raise CollectorUnavailable("INVALID_VALUE") from exc
    return -parsed if negative else parsed


class FarsideEtfCollector:
    def __init__(self, asset: str, *, transport: Transport | None = None) -> None:
        self.asset = asset.upper()
        if self.asset not in _SOURCE_BY_ASSET:
            raise ValueError("unsupported_etf_asset")
        self.source = source_for_code(_SOURCE_BY_ASSET[self.asset])
        self.transport = transport or RequestsTransport()

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        url = self.source.urls[0]
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=10_000_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            html = response.body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        parser = _TableParser()
        parser.feed(html)
        tables = [table for table in parser.tables if table and {cell.casefold() for cell in table[0]} >= {"date", "total"}]
        if len(tables) != 1:
            raise CollectorUnavailable("SCHEMA_DRIFT")
        table = tables[0]
        header = {name.casefold(): index for index, name in enumerate(table[0])}
        date_index, total_index = header["date"], header["total"]
        cutoff = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        rows: list[Observation] = []
        seen: set[datetime] = set()
        for cells in table[1:]:
            if len(cells) <= max(date_index, total_index):
                raise CollectorUnavailable("SCHEMA_DRIFT")
            effective_at = _date(cells[date_index])
            if effective_at in seen:
                raise CollectorUnavailable("DUPLICATE_PERIOD")
            seen.add(effective_at)
            if effective_at >= cutoff:
                continue
            value = _millions(cells[total_index])
            rows.append(
                Observation.create(
                    source_code=self.source.code,
                    source_url=url,
                    market=self.source.market,
                    symbol=self.asset,
                    effective_at=effective_at,
                    observed_at=as_of,
                    methodology_version=self.source.methodology_version,
                    value={"metric": "crypto.etf.net_flow_usd", "value": str(value), "unit": "USD", "dimensions": {"asset": self.asset, "fund": "TOTAL"}},
                    data_class="LIVE",
                )
            )
        if not rows:
            raise CollectorUnavailable("SCHEMA_DRIFT")
        return tuple(sorted(rows, key=lambda row: row.effective_at))


__all__ = ["FarsideEtfCollector"]
