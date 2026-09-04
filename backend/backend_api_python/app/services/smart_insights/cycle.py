"""Cycle indicators ported from the legacy DataVest public-source contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport, Transport


def _decimal(value: object) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise CollectorUnavailable("INVALID_VALUE") from exc
    if not parsed.is_finite():
        raise CollectorUnavailable("INVALID_VALUE")
    return parsed


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


__all__ = ["AltcoinSeasonCollector"]
