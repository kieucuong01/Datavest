"""Bybit public derivatives evidence collector with cursor-bounded history."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Protocol
from urllib.parse import urlencode

from .collectors import CollectorUnavailable
from .contracts import Observation
from .derivatives import DerivativeBackfillRequest, DerivativeCoverage, OI_NATIVE
from .sources import source_for_code
from .transport import RequestsTransport, Transport


UTC = timezone.utc


class BybitClient(Protocol):
    def get(self, path: str, params: Mapping[str, object]) -> Mapping[str, object]: ...


class BybitDerivativesUnavailable(CollectorUnavailable):
    pass


class BybitPublicClient:
    """Small bounded adapter for the unauthenticated Bybit V5 market API."""

    base_url = "https://api.bybit.com"

    def __init__(self, *, transport: Transport | None = None) -> None:
        self.transport = transport or RequestsTransport()

    def get(self, path: str, params: Mapping[str, object]) -> Mapping[str, object]:
        url = f"{self.base_url}{path}?{urlencode(params)}"
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=2_000_000)
        if response.status != 200 or response.url != url:
            raise BybitDerivativesUnavailable("INVALID_RESPONSE")
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BybitDerivativesUnavailable("INVALID_RESPONSE") from exc
        if not isinstance(payload, Mapping) or payload.get("retCode") not in (0, "0", None):
            raise BybitDerivativesUnavailable("INVALID_RESPONSE")
        return payload


def _decimal(value: object, error: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise BybitDerivativesUnavailable(error) from exc
    if not parsed.is_finite() or parsed < 0:
        raise BybitDerivativesUnavailable(error)
    return parsed


def _timestamp(value: object) -> datetime:
    try:
        millis = int(str(value))
    except (TypeError, ValueError) as exc:
        raise BybitDerivativesUnavailable("INVALID_TIMESTAMP") from exc
    return datetime.fromtimestamp(millis / 1000, tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)


class BybitDerivativesCollector:
    source_code = "bybit-derivatives"

    def __init__(self, *, client: BybitClient | None = None) -> None:
        self.client = client or BybitPublicClient()
        self.source = source_for_code(self.source_code)

    def backfill_open_interest(
        self, request: DerivativeBackfillRequest
    ) -> tuple[tuple[Observation, ...], tuple[DerivativeCoverage, ...]]:
        if request.source != self.source_code:
            raise ValueError("source mismatch")
        observations: list[Observation] = []
        coverage: list[DerivativeCoverage] = []
        for symbol in request.symbols:
            cursor = ""
            rows_for_symbol: list[Observation] = []
            while True:
                params: dict[str, object] = {
                    "category": "linear",
                    "symbol": f"{symbol.upper()}USDT",
                    "intervalTime": "1d",
                    "startTime": int(request.start.timestamp() * 1000),
                    "endTime": int(request.end.timestamp() * 1000),
                    "limit": 200,
                }
                if cursor:
                    params["cursor"] = cursor
                payload = self.client.get("/v5/market/open-interest", params)
                result = payload.get("result") if isinstance(payload, Mapping) else None
                items = result.get("list") if isinstance(result, Mapping) else None
                if not isinstance(items, list):
                    raise BybitDerivativesUnavailable("SCHEMA_DRIFT")
                for item in items:
                    if not isinstance(item, Mapping):
                        raise BybitDerivativesUnavailable("SCHEMA_DRIFT")
                    effective_at = _timestamp(item.get("timestamp"))
                    value = _decimal(item.get("openInterest"), "INVALID_OPEN_INTEREST")
                    rows_for_symbol.append(
                        Observation.create(
                            source_code=self.source.code,
                            source_url=self.source.urls[0],
                            market=self.source.market,
                            symbol=symbol,
                            effective_at=effective_at,
                            observed_at=request.end.astimezone(UTC),
                            methodology_version=self.source.methodology_version,
                            value={
                                "metric": OI_NATIVE,
                                "value": str(value),
                                "unit": symbol.upper(),
                                "dimensions": {"venue": "bybit", "frequency": "daily", "contract": "linear"},
                                "evidenceOnly": True,
                            },
                            data_class="LIVE",
                        )
                    )
                next_cursor = result.get("nextPageCursor") if isinstance(result, Mapping) else ""
                if not next_cursor:
                    break
                if not isinstance(next_cursor, str):
                    raise BybitDerivativesUnavailable("SCHEMA_DRIFT")
                cursor = next_cursor
            if rows_for_symbol:
                points = sorted(rows_for_symbol, key=lambda row: row.effective_at)
                observations.extend(points)
                coverage.append(
                    DerivativeCoverage(
                        source=self.source.code,
                        metric=OI_NATIVE,
                        symbol=symbol,
                        start=points[0].effective_at,
                        end=points[-1].effective_at,
                        history_limited=False,
                    )
                )
        return tuple(observations), tuple(coverage)

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        """Collect a revision-safe seven-day OI window for the daily scheduler."""
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        observed_at = as_of.astimezone(UTC)
        request = DerivativeBackfillRequest(
            source=self.source_code,
            symbols=("BTC", "ETH", "SOL"),
            start=observed_at.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7),
            end=observed_at,
        )
        rows, _coverage = self.backfill_open_interest(request)
        return rows


__all__ = ["BybitDerivativesCollector", "BybitDerivativesUnavailable", "BybitPublicClient"]
