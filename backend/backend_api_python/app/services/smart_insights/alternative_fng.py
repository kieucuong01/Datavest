"""Alternative.me Fear & Greed collector with a strict JSON contract."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport, Transport


class AlternativeFearGreedCollector:
    def __init__(self, *, transport: Transport | None = None) -> None:
        self.source = source_for_code("alternative-fng")
        self.transport = transport or RequestsTransport()

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        url = self.source.urls[0]
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=5_000_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise CollectorUnavailable("SCHEMA_DRIFT")
        cutoff = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        seen: set[datetime] = set()
        rows: list[Observation] = []
        for item in payload["data"]:
            if not isinstance(item, dict):
                raise CollectorUnavailable("SCHEMA_DRIFT")
            try:
                effective_at = datetime.fromtimestamp(int(str(item["timestamp"])), timezone.utc)
                value = Decimal(str(item["value"]))
            except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError, OSError) as exc:
                raise CollectorUnavailable("INVALID_VALUE") from exc
            if effective_at != effective_at.replace(hour=0, minute=0, second=0, microsecond=0):
                raise CollectorUnavailable("INVALID_TIMESTAMP")
            if effective_at in seen:
                raise CollectorUnavailable("DUPLICATE_PERIOD")
            seen.add(effective_at)
            if effective_at >= cutoff or not value.is_finite() or value < 0 or value > 100:
                continue
            rows.append(
                Observation.create(
                    source_code=self.source.code,
                    source_url=url,
                    market=self.source.market,
                    effective_at=effective_at,
                    observed_at=as_of,
                    methodology_version=self.source.methodology_version,
                    value={
                        "metric": "crypto.fear_greed.index",
                        "value": str(value),
                        "unit": "index",
                        "dimensions": {"classification": str(item.get("value_classification") or "")},
                    },
                    data_class="LIVE",
                )
            )
        return tuple(sorted(rows, key=lambda row: row.effective_at))


__all__ = ["AlternativeFearGreedCollector"]
