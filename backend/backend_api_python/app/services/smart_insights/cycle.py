"""Cycle indicators ported from the legacy DataVest public-source contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport, Transport


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


def _decimal(value: object) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise CollectorUnavailable("INVALID_VALUE") from exc
    if not parsed.is_finite():
        raise CollectorUnavailable("INVALID_VALUE")
    return parsed


class CbbiCollector:
    def __init__(self, *, transport: Transport | None = None) -> None:
        self.source = source_for_code("cbbi-public")
        self.transport = transport or RequestsTransport()

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        url = self.source.urls[1]
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=5_000_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("Confidence"), dict):
            raise CollectorUnavailable("SCHEMA_DRIFT")
        cutoff = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        rows: list[Observation] = []
        seen: set[datetime] = set()
        for raw_timestamp, confidence in payload["Confidence"].items():
            try:
                effective_at = datetime.fromtimestamp(int(str(raw_timestamp)), timezone.utc)
            except (TypeError, ValueError, OverflowError, OSError) as exc:
                raise CollectorUnavailable("INVALID_TIMESTAMP") from exc
            if effective_at in seen:
                raise CollectorUnavailable("DUPLICATE_PERIOD")
            seen.add(effective_at)
            if effective_at >= cutoff:
                continue
            values = [("crypto.cycle.cbbi.confidence", _decimal(confidence))]
            for field, component in _CBBI_COMPONENTS.items():
                series = payload.get(field)
                if isinstance(series, dict) and series.get(raw_timestamp) is not None:
                    values.append((f"crypto.cycle.cbbi.component.{component}", _decimal(series[raw_timestamp])))
            for metric, value in values:
                rows.append(
                    Observation.create(
                        source_code=self.source.code,
                        source_url=url,
                        market=self.source.market,
                        symbol="BTC",
                        effective_at=effective_at,
                        observed_at=as_of,
                        methodology_version=self.source.methodology_version,
                        value={"metric": metric, "value": str(value), "unit": "index", "dimensions": {"index": "CBBI"}},
                        data_class="LIVE",
                    )
                )
        if not rows:
            raise CollectorUnavailable("SCHEMA_DRIFT")
        return tuple(sorted(rows, key=lambda row: (row.effective_at, row.value["metric"])))


class AltcoinSeasonCollector:
    def __init__(self, *, transport: Transport | None = None) -> None:
        self.source = source_for_code("blockchaincenter-altcoin-season")
        self.transport = transport or RequestsTransport()

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        url = self.source.urls[0]
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=5_000_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            html = response.body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        matches = dict(re.findall(r"\b(Altcoin Season|Month|Year)\s*\(\s*(\d{1,3})\s*\)", html, flags=re.IGNORECASE))
        if set(matches) != {"Altcoin Season", "Month", "Year"}:
            raise CollectorUnavailable("SCHEMA_DRIFT")
        metrics = (
            ("crypto.cycle.altcoin_season.index", matches["Altcoin Season"]),
            ("crypto.cycle.altcoin_season.month_index", matches["Month"]),
            ("crypto.cycle.altcoin_season.year_index", matches["Year"]),
        )
        effective_at = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return tuple(
            Observation.create(
                source_code=self.source.code,
                source_url=url,
                market=self.source.market,
                effective_at=effective_at,
                observed_at=as_of,
                methodology_version=self.source.methodology_version,
                value={"metric": metric, "value": str(_decimal(value)), "unit": "index", "dimensions": {"horizon": horizon}},
                data_class="LIVE",
            )
            for metric, value, horizon in (
                (metrics[0][0], metrics[0][1], "season_90d"),
                (metrics[1][0], metrics[1][1], "month"),
                (metrics[2][0], metrics[2][1], "year"),
            )
        )


__all__ = ["AltcoinSeasonCollector", "CbbiCollector"]
