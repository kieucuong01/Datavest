"""CoinGlass HTML collectors ported from the legacy DataVest worker.

CoinGlass serves these tables from the public page response in the current
deployment.  The parser stays stdlib-only and fails closed on schema drift;
the browser-rendered collector used by the old worker is therefore not needed
for this local/runtime path while the table is server-rendered.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport, Transport


_MARGIN_HEADERS = (
    "Time",
    "Annualized Interest Rate",
    "Daily Interest Rate",
    "Hourly Interest Rate",
)
_LEGACY_MAXPAIN_HEADERS = (
    "Coin",
    "Current Price",
    "Short Max Pain Price",
    "Short Distance",
    "Short Max Pain Level",
    "Long Max Pain Price",
    "Long Distance",
    "Long Max Pain Level",
)
_MAXPAIN_HEADERS = (
    "",
    "Ranking",
    "Symbol",
    "Price",
    "Short Max Pain",
    "Short Distance",
    "Long Max Pain",
    "Long Distance",
)
_DEFAULT_SYMBOLS = frozenset({"BTC", "ETH", "SOL"})


def _text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag == "table":
            if self._table is not None:
                raise ValueError("SCHEMA_DRIFT")
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
            self._row.append(_text(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _matching_table(html: str, headers: tuple[str, ...]) -> list[list[str]]:
    if not html.strip():
        raise CollectorUnavailable("SCHEMA_DRIFT")
    parser = _TableParser()
    try:
        parser.feed(html)
        parser.close()
    except ValueError:
        raise
    except Exception as exc:
        raise CollectorUnavailable("SCHEMA_DRIFT") from exc
    matching = [table for table in parser.tables if table and tuple(table[0]) == headers]
    if len(matching) != 1:
        raise CollectorUnavailable("SCHEMA_DRIFT")
    return matching[0]


def _percent(text: str) -> Decimal:
    if not text.endswith("%"):
        raise CollectorUnavailable("INVALID_VALUE")
    try:
        value = Decimal(text[:-1])
    except InvalidOperation as exc:
        raise CollectorUnavailable("INVALID_VALUE") from exc
    if not value.is_finite():
        raise CollectorUnavailable("INVALID_VALUE")
    return value


def _compact_usd(text: str) -> Decimal:
    cleaned = text.replace(",", "").replace("$", "").strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1].strip()
    multiplier = Decimal("1")
    if cleaned[-1:] in {"K", "M", "B"}:
        multiplier = {"K": Decimal("1000"), "M": Decimal("1000000"), "B": Decimal("1000000000")}[cleaned[-1]]
        cleaned = cleaned[:-1]
    try:
        value = Decimal(cleaned) * multiplier
    except (InvalidOperation, ValueError) as exc:
        raise CollectorUnavailable("INVALID_VALUE") from exc
    if negative:
        value = -value
    if not value.is_finite():
        raise CollectorUnavailable("INVALID_VALUE")
    return value


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    return value.astimezone(timezone.utc)


def _parse_margin(html: str, observed_at: datetime) -> tuple[tuple[str, Decimal, datetime], ...]:
    observed = _aware_utc(observed_at)
    table = _matching_table(html, _MARGIN_HEADERS)
    seen: set[datetime] = set()
    result: list[tuple[str, Decimal, datetime]] = []
    for cells in table[1:]:
        if len(cells) != len(_MARGIN_HEADERS) or not all(cells):
            raise CollectorUnavailable("SCHEMA_DRIFT")
        try:
            effective_at = datetime.strptime(cells[0], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise CollectorUnavailable("INVALID_TIMESTAMP") from exc
        if effective_at.minute or effective_at.second or effective_at.microsecond:
            raise CollectorUnavailable("INVALID_TIMESTAMP")
        if effective_at > observed + timedelta(minutes=5) or effective_at in seen:
            raise CollectorUnavailable("INVALID_TIMESTAMP")
        seen.add(effective_at)
        for metric, value in zip(
            (
                "crypto.derivatives.margin_borrow.annualized_rate",
                "crypto.derivatives.margin_borrow.daily_rate",
                "crypto.derivatives.margin_borrow.hourly_rate",
            ),
            (_percent(cells[1]), _percent(cells[2]), _percent(cells[3])),
            strict=True,
        ):
            result.append((metric, value, effective_at))
    if not result:
        raise CollectorUnavailable("SCHEMA_DRIFT")
    return tuple(result)


def _parse_grouped_side(text: str) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    parts = text.split()
    if len(parts) == 5 and parts[-1] == "💥":
        parts.pop()
    if len(parts) != 4:
        raise CollectorUnavailable("SCHEMA_DRIFT")
    price, level, absolute_distance, distance = parts
    return _compact_usd(price), _compact_usd(level), _compact_usd(absolute_distance), _percent(distance) / Decimal("100")


def _parse_maxpain(html: str, observed_at: datetime, symbols: frozenset[str]) -> tuple[tuple[str, str, Decimal, dict[str, str]], ...]:
    observed = _aware_utc(observed_at)
    try:
        table = _matching_table(html, _MAXPAIN_HEADERS)
        grouped = True
    except CollectorUnavailable:
        table = _matching_table(html, _LEGACY_MAXPAIN_HEADERS)
        grouped = False
    seen: set[str] = set()
    result: list[tuple[str, str, Decimal, dict[str, str]]] = []
    for cells in table[1:]:
        if grouped:
            if len(cells) != 6 or cells[0] or not all(cells[1:]) or not cells[1].isdigit():
                raise CollectorUnavailable("SCHEMA_DRIFT")
            symbol = cells[2].upper()
            current = _compact_usd(cells[3])
            short_price, short_level, short_absolute, short_distance = _parse_grouped_side(cells[4])
            long_price, long_level, long_absolute, long_distance = _parse_grouped_side(cells[5])
            if abs(short_absolute - (short_price - current)) > Decimal("0.02") or abs(long_absolute - (long_price - current)) > Decimal("0.02"):
                raise CollectorUnavailable("INVALID_DISTANCE")
        else:
            if len(cells) != len(_LEGACY_MAXPAIN_HEADERS) or not all(cells):
                raise CollectorUnavailable("SCHEMA_DRIFT")
            symbol = cells[0].upper()
            current = _compact_usd(cells[1])
            short_price = _compact_usd(cells[2])
            short_distance = _percent(cells[3]) / Decimal("100")
            short_level = _compact_usd(cells[4])
            long_price = _compact_usd(cells[5])
            long_distance = _percent(cells[6]) / Decimal("100")
            long_level = _compact_usd(cells[7])
        if symbol not in symbols:
            continue
        if symbol in seen:
            raise CollectorUnavailable("DUPLICATE_ASSET")
        seen.add(symbol)
        if current <= 0 or min(short_price, short_level, long_price, long_level) < 0:
            raise CollectorUnavailable("INVALID_VALUE")
        if abs(short_distance - (short_price - current) / current) > Decimal("0.0002") or abs(long_distance - (long_price - current) / current) > Decimal("0.0002"):
            raise CollectorUnavailable("INVALID_DISTANCE")
        common = {"range": "24h"}
        values = (
            ("crypto.derivatives.liquidation.current_price_usd", current, common),
            ("crypto.derivatives.liquidation.short_max_pain_price_usd", short_price, {**common, "side": "short"}),
            ("crypto.derivatives.liquidation.short_distance_ratio", short_distance, {**common, "side": "short"}),
            ("crypto.derivatives.liquidation.short_max_pain_level_usd", short_level, {**common, "side": "short"}),
            ("crypto.derivatives.liquidation.long_max_pain_price_usd", long_price, {**common, "side": "long"}),
            ("crypto.derivatives.liquidation.long_distance_ratio", long_distance, {**common, "side": "long"}),
            ("crypto.derivatives.liquidation.long_max_pain_level_usd", long_level, {**common, "side": "long"}),
        )
        result.extend((metric, symbol, value, dimensions) for metric, value, dimensions in values)
    if not result:
        raise CollectorUnavailable("SCHEMA_DRIFT")
    return tuple(result)


class CoinGlassMarginCollector:
    source_code = "coinglass-margin-borrow"

    def __init__(self, *, transport: Transport | None = None) -> None:
        self.source = source_for_code(self.source_code)
        self.transport = transport or RequestsTransport()

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        _aware_utc(as_of)
        url = self.source.urls[0]
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=10_000_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            values = _parse_margin(response.body.decode("utf-8"), response_observed := as_of)
        except UnicodeDecodeError as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        return tuple(
            Observation.create(
                source_code=self.source.code,
                source_url=url,
                market=self.source.market,
                effective_at=effective_at,
                observed_at=response_observed,
                methodology_version=self.source.methodology_version,
                value={"metric": metric, "value": str(value), "unit": "percent", "dimensions": {"exchange": "Binance", "quote_asset": "USDT"}},
                data_class="LIVE",
            )
            for metric, value, effective_at in values
        )


class CoinGlassMaxPainCollector:
    source_code = "coinglass-liquidation-maxpain"

    def __init__(self, *, transport: Transport | None = None, symbols: frozenset[str] = _DEFAULT_SYMBOLS) -> None:
        if not symbols:
            raise ValueError("At least one crypto symbol is required")
        self.source = source_for_code(self.source_code)
        self.transport = transport or RequestsTransport()
        self.symbols = symbols

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        observed = _aware_utc(as_of)
        url = self.source.urls[0]
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=10_000_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            values = _parse_maxpain(response.body.decode("utf-8"), observed, self.symbols)
        except UnicodeDecodeError as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        return tuple(
            Observation.create(
                source_code=self.source.code,
                source_url=url,
                market=self.source.market,
                symbol=symbol,
                effective_at=observed,
                observed_at=observed,
                methodology_version=self.source.methodology_version,
                value={"metric": metric, "value": str(value), "unit": "ratio" if "distance" in metric else "USD", "dimensions": dimensions},
                data_class="LIVE",
            )
            for metric, symbol, value, dimensions in values
        )


__all__ = ["CoinGlassMarginCollector", "CoinGlassMaxPainCollector"]
