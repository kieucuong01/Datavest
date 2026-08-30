"""Allow-listed FRED public CSV collector ported from DataVest."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO
from types import MappingProxyType
from urllib.parse import urlencode

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport, Transport


@dataclass(frozen=True, slots=True)
class FredSeries:
    metric: str
    unit: str
    frequency: str


FRED_SERIES = MappingProxyType(
    {
        "DGS2": FredSeries("macro.yield.2y_pct", "%", "daily"),
        "DGS10": FredSeries("macro.yield.10y_pct", "%", "daily"),
        "DFII10": FredSeries("macro.real_yield.10y_pct", "%", "daily"),
        "DFF": FredSeries("macro.fed_funds_pct", "%", "daily"),
        "SOFR": FredSeries("macro.sofr_pct", "%", "daily"),
        "WALCL": FredSeries("macro.fed_balance_sheet_musd", "USD million", "weekly"),
        "DTWEXBGS": FredSeries("macro.usd_broad_index", "index", "daily"),
        "CPIAUCSL": FredSeries("macro.cpi_index", "index", "monthly"),
        "CPILFESL": FredSeries("macro.core_cpi_index", "index", "monthly"),
        "PCEPI": FredSeries("macro.pce_index", "index", "monthly"),
        "PAYEMS": FredSeries("macro.payroll_thousands", "thousand", "monthly"),
        "UNRATE": FredSeries("macro.unemployment_pct", "%", "monthly"),
        "GDP": FredSeries("macro.gdp_busd", "USD billion", "quarterly"),
        "M2SL": FredSeries("macro.m2_busd", "USD billion", "weekly"),
    }
)


class FredCollector:
    def __init__(self, *, transport: Transport | None = None, clock=None) -> None:
        self.source = source_for_code("fred")
        self.transport = transport or RequestsTransport()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def collect(self, series_id: str, start: date, end: date) -> tuple[Observation, ...]:
        if series_id not in FRED_SERIES:
            raise ValueError("FRED series must be allow-listed")
        if start > end:
            raise ValueError("invalid_observation_range")
        series = FRED_SERIES[series_id]
        base_url = self.source.urls[0]
        request_url = f"{base_url}?{urlencode({'id': series_id, 'cosd': start.isoformat(), 'coed': end.isoformat()})}"
        response = self.transport.fetch(request_url, timeout_seconds=30, max_bytes=10_000_000)
        if response.status != 200 or response.url != request_url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            reader = csv.DictReader(StringIO(response.body.decode("utf-8-sig")))
            if reader.fieldnames != ["observation_date", series_id]:
                raise CollectorUnavailable("SCHEMA_DRIFT")
            raw_rows = list(reader)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        if len(raw_rows) > 50_000:
            raise CollectorUnavailable("RESPONSE_TOO_LARGE")
        observed_at = self.clock()
        result: list[Observation] = []
        seen: set[date] = set()
        for row in raw_rows:
            try:
                effective_date = date.fromisoformat(str(row.get("observation_date")))
            except ValueError as exc:
                raise CollectorUnavailable("INVALID_TIMESTAMP") from exc
            if effective_date in seen:
                raise CollectorUnavailable("DUPLICATE_PERIOD")
            seen.add(effective_date)
            if not start <= effective_date <= end:
                raise CollectorUnavailable("OUT_OF_RANGE")
            raw_value = row.get(series_id)
            if raw_value in (None, "", "."):
                continue
            try:
                value = Decimal(raw_value)
            except InvalidOperation as exc:
                raise CollectorUnavailable("INVALID_VALUE") from exc
            if not value.is_finite():
                raise CollectorUnavailable("INVALID_VALUE")
            result.append(
                Observation.create(
                    source_code=self.source.code,
                    source_url=base_url,
                    market=self.source.market,
                    effective_at=datetime.combine(effective_date, datetime.min.time(), tzinfo=timezone.utc),
                    observed_at=observed_at,
                    methodology_version=self.source.methodology_version,
                    value={
                        "metric": series.metric,
                        "value": str(value),
                        "unit": series.unit,
                        "dimensions": {"providerSeries": series_id, "frequency": series.frequency},
                    },
                    data_class="LIVE",
                )
            )
        return tuple(result)


__all__ = ["FRED_SERIES", "FredCollector", "FredSeries"]
