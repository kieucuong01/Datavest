"""mempool.space public API collector; no watchlists or address tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport, Transport


def _decimal(value: object) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise CollectorUnavailable("INVALID_VALUE") from exc
    if not parsed.is_finite() or parsed < 0:
        raise CollectorUnavailable("INVALID_VALUE")
    return parsed


class MempoolCollector:
    def __init__(self, *, transport: Transport | None = None) -> None:
        self.source = source_for_code("mempool-space")
        self.transport = transport or RequestsTransport()

    def _json(self, url: str) -> object:
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=5_000_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            return json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc

    def _text_decimal(self, url: str) -> Decimal:
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=1_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            value = response.body.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        return _decimal(value)

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        observed_at = as_of.astimezone(timezone.utc)
        fees_url, mempool_url, hashrate_url, height_url = self.source.urls
        fees, mempool, hashrate = self._json(fees_url), self._json(mempool_url), self._json(hashrate_url)
        if not isinstance(fees, dict) or not isinstance(mempool, dict) or not isinstance(hashrate, dict):
            raise CollectorUnavailable("SCHEMA_DRIFT")
        values: list[tuple[str, Decimal, str, datetime, str]] = []
        for field, metric in (
            ("fastestFee", "crypto.mempool.fastest_fee_sat_vb"),
            ("halfHourFee", "crypto.mempool.half_hour_fee_sat_vb"),
            ("hourFee", "crypto.mempool.hour_fee_sat_vb"),
            ("minimumFee", "crypto.mempool.minimum_fee_sat_vb"),
        ):
            values.append((metric, _decimal(fees.get(field)), "sat/vB", observed_at, fees_url))
        for field, metric, unit in (
            ("count", "crypto.mempool.tx_count", "count"),
            ("vsize", "crypto.mempool.virtual_size_vb", "vB"),
            ("total_fee", "crypto.mempool.total_fee_sat", "sat"),
        ):
            values.append((metric, _decimal(mempool.get(field)), unit, observed_at, mempool_url))
        points = hashrate.get("hashrates")
        if not isinstance(points, list) or not points:
            raise CollectorUnavailable("SCHEMA_DRIFT")
        latest = points[-1]
        if not isinstance(latest, list | tuple) or len(latest) < 2:
            raise CollectorUnavailable("SCHEMA_DRIFT")
        try:
            timestamp = int(latest[0])
            effective_at = datetime.fromtimestamp(timestamp, timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError) as exc:
            raise CollectorUnavailable("INVALID_TIMESTAMP") from exc
        values.append(("crypto.mining.hashrate_hs", _decimal(latest[1]), "H/s", effective_at, hashrate_url))
        values.append(("crypto.chain.block_height", self._text_decimal(height_url), "count", observed_at, height_url))
        return tuple(
            Observation.create(
                source_code=self.source.code,
                source_url=url,
                market=self.source.market,
                effective_at=effective_at,
                observed_at=observed_at,
                methodology_version=self.source.methodology_version,
                value={"metric": metric, "value": str(value), "unit": unit, "dimensions": {"network": "bitcoin"}},
                data_class="LIVE",
            )
            for metric, value, unit, effective_at, url in values
        )


__all__ = ["MempoolCollector"]
