"""DefiLlama stablecoin supply collector ported from DataVest."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code
from .transport import RequestsTransport, Transport


def _number(value: object) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise CollectorUnavailable("INVALID_VALUE") from exc
    if not parsed.is_finite() or parsed < 0:
        raise CollectorUnavailable("INVALID_VALUE")
    return parsed


class DefiLlamaStablecoinsCollector:
    def __init__(self, *, transport: Transport | None = None) -> None:
        self.source = source_for_code("defillama-stablecoins")
        self.transport = transport or RequestsTransport()

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        url = self.source.urls[0]
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=10_000_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        if not isinstance(payload, list):
            raise CollectorUnavailable("SCHEMA_DRIFT")
        cutoff = as_of.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result: list[Observation] = []
        seen: set[datetime] = set()
        for row in payload:
            if not isinstance(row, dict) or not isinstance(row.get("totalCirculatingUSD"), dict):
                raise CollectorUnavailable("SCHEMA_DRIFT")
            try:
                effective_at = datetime.fromtimestamp(int(str(row["date"])), timezone.utc)
            except (KeyError, ValueError, OverflowError, OSError) as exc:
                raise CollectorUnavailable("INVALID_TIMESTAMP") from exc
            if effective_at in seen:
                raise CollectorUnavailable("DUPLICATE_SERIES")
            seen.add(effective_at)
            if effective_at >= cutoff:
                continue
            buckets = row["totalCirculatingUSD"]
            total = sum((_number(value) for value in buckets.values()), Decimal("0"))
            result.append(
                Observation.create(
                    source_code=self.source.code,
                    source_url=url,
                    market=self.source.market,
                    effective_at=effective_at,
                    observed_at=as_of,
                    methodology_version=self.source.methodology_version,
                    value={
                        "metric": "crypto.stablecoin.supply_usd",
                        "value": str(total),
                        "unit": "USD",
                        "dimensions": {"scope": "all", "frequency": "daily", "pegBuckets": len(buckets)},
                    },
                    data_class="LIVE",
                )
            )
        return tuple(sorted(result, key=lambda row: row.effective_at))


class DefiLlamaChainsCollector:
    """Fetch the current chain TVL table and preserve a TOTAL row."""

    def __init__(self, *, transport: Transport | None = None) -> None:
        self.source = source_for_code("defillama-chains")
        self.transport = transport or RequestsTransport()

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        url = self.source.urls[0]
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=10_000_000)
        if response.status != 200 or response.url != url:
            raise CollectorUnavailable("INVALID_RESPONSE")
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectorUnavailable("INVALID_RESPONSE") from exc
        if not isinstance(payload, list):
            raise CollectorUnavailable("SCHEMA_DRIFT")

        observations: list[Observation] = []
        names: set[str] = set()
        total = Decimal("0")
        for row in payload:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str):
                raise CollectorUnavailable("SCHEMA_DRIFT")
            name = row["name"].strip()
            normalized = name.casefold()
            if not name or normalized in names:
                raise CollectorUnavailable("DUPLICATE_SERIES")
            names.add(normalized)
            value = _number(row.get("tvl"))
            total += value
            dimensions = {"chain": name, "frequency": "observed_daily"}
            token_symbol = row.get("tokenSymbol")
            if isinstance(token_symbol, str) and token_symbol.strip():
                dimensions["tokenSymbol"] = token_symbol.strip()
            observations.append(
                Observation.create(
                    source_code=self.source.code,
                    source_url=url,
                    market=self.source.market,
                    effective_at=as_of,
                    observed_at=as_of,
                    methodology_version=self.source.methodology_version,
                    value={
                        "metric": "crypto.defi.chain_tvl_usd",
                        "value": str(value),
                        "unit": "USD",
                        "dimensions": dimensions,
                    },
                    data_class="LIVE",
                )
            )
        observations.append(
            Observation.create(
                source_code=self.source.code,
                source_url=url,
                market=self.source.market,
                effective_at=as_of,
                observed_at=as_of,
                methodology_version=self.source.methodology_version,
                value={
                    "metric": "crypto.defi.chain_tvl_usd",
                    "value": str(total),
                    "unit": "USD",
                    "dimensions": {"chain": "TOTAL", "frequency": "observed_daily"},
                },
                data_class="LIVE",
            )
        )
        return tuple(observations)


__all__ = ["DefiLlamaChainsCollector", "DefiLlamaStablecoinsCollector"]
