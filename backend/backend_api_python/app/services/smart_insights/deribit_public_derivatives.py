"""Daily BTC/ETH options and futures structure from Deribit's public API."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Protocol
from urllib.parse import urlencode

from .collectors import CollectorUnavailable
from .contracts import Observation
from .derivatives import CALL_OI, FAR_BASIS, NEAR_BASIS, OPTIONS_ASSETS, PUT_CALL_OI_RATIO, PUT_OI, daily_effective_at
from .sources import source_for_code
from .transport import RequestsTransport, Transport


UTC = timezone.utc


class DeribitClient(Protocol):
    def get(self, method: str, params: Mapping[str, object]) -> object: ...


class DeribitPublicUnavailable(CollectorUnavailable):
    pass


class DeribitPublicClient:
    base_url = "https://www.deribit.com/api/v2/public"

    def __init__(self, *, transport: Transport | None = None) -> None:
        self.transport = transport or RequestsTransport()

    def get(self, method: str, params: Mapping[str, object]) -> object:
        url = f"{self.base_url}/{method}?{urlencode(params)}"
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=4_000_000)
        if response.status != 200 or response.url != url:
            raise DeribitPublicUnavailable("INVALID_RESPONSE")
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeribitPublicUnavailable("INVALID_RESPONSE") from exc
        if not isinstance(payload, Mapping) or not isinstance(payload.get("result"), list):
            raise DeribitPublicUnavailable("SCHEMA_DRIFT")
        return payload["result"]


def _decimal(value: object, error: str, *, positive: bool = False) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise DeribitPublicUnavailable(error) from exc
    if not parsed.is_finite() or (positive and parsed <= 0) or (not positive and parsed < 0):
        raise DeribitPublicUnavailable(error)
    return parsed


def _timestamp(value: object) -> datetime:
    try:
        return datetime.fromtimestamp(int(str(value)) / 1000, UTC)
    except (TypeError, ValueError, OSError) as exc:
        raise DeribitPublicUnavailable("INVALID_TIMESTAMP") from exc


def _expiry_from_instrument(name: str, timestamp: object) -> datetime | None:
    if timestamp is not None:
        return _timestamp(timestamp)
    parts = name.split("-")
    if len(parts) < 2:
        return None
    try:
        # Book summaries omit expiration_timestamp; futures instrument names
        # carry the UTC expiry date as BTC-31AUG26.
        return datetime.strptime(parts[1].upper(), "%d%b%y").replace(tzinfo=UTC)
    except ValueError:
        return None


class DeribitPublicDerivativesCollector:
    source_code = "deribit-public-derivatives"

    def __init__(self, *, client: DeribitClient | None = None) -> None:
        self.client = client or DeribitPublicClient()
        self.source = source_for_code(self.source_code)

    def _row(self, *, symbol: str, metric: str, value: Decimal, unit: str, effective_at: datetime, observed_at: datetime, endpoint: str) -> Observation:
        return Observation.create(
            source_code=self.source_code, source_url=f"{self.source.urls[0].rstrip('/')}/{endpoint}",
            market="crypto", symbol=symbol, effective_at=effective_at, observed_at=observed_at,
            methodology_version=self.source.methodology_version,
            value={"metric": metric, "value": str(value), "unit": unit, "dimensions": {"venue": "deribit", "frequency": "daily"}, "evidenceOnly": True},
            data_class="LIVE",
        )

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        observed_at = as_of.astimezone(UTC)
        effective_at = daily_effective_at(observed_at)
        rows: list[Observation] = []
        for symbol in OPTIONS_ASSETS:
            futures = self.client.get("get_book_summary_by_currency", {"currency": symbol, "kind": "future"})
            options = self.client.get("get_book_summary_by_currency", {"currency": symbol, "kind": "option"})
            rows.extend(self._futures(symbol, futures, effective_at, observed_at))
            rows.extend(self._options(symbol, options, effective_at, observed_at))
        return tuple(rows)

    def _futures(self, symbol: str, raw: object, effective_at: datetime, observed_at: datetime) -> tuple[Observation, ...]:
        if not isinstance(raw, list): raise DeribitPublicUnavailable("SCHEMA_DRIFT")
        perpetual = None
        dated = []
        for item in raw:
            if not isinstance(item, Mapping): raise DeribitPublicUnavailable("SCHEMA_DRIFT")
            name = str(item.get("instrument_name") or "")
            if name.endswith("-PERPETUAL"):
                perpetual = item
            else:
                expiry = _expiry_from_instrument(name, item.get("expiration_timestamp"))
                if expiry is not None and expiry > observed_at:
                    dated.append((expiry, item))
        if perpetual is None or len(dated) < 2: raise DeribitPublicUnavailable("FUTURES_COVERAGE_INCOMPLETE")
        spot = _decimal(perpetual.get("estimated_delivery_price"), "INVALID_FUTURES", positive=True)
        dated.sort(key=lambda item: item[0])
        choices = (dated[0], next((item for item in dated if (item[0] - observed_at).days >= 30), dated[-1]))
        result = []
        for metric, (expiry, item) in zip((NEAR_BASIS, FAR_BASIS), choices):
            days = max(1, (expiry - observed_at).total_seconds() / 86_400)
            future = _decimal(item.get("mark_price"), "INVALID_FUTURES", positive=True)
            basis = (future / spot - Decimal("1")) * Decimal("365") / Decimal(str(days))
            if abs(basis) > Decimal("5"): raise DeribitPublicUnavailable("INVALID_FUTURES")
            result.append(self._row(symbol=symbol, metric=metric, value=basis, unit="return", effective_at=effective_at, observed_at=observed_at, endpoint="get_book_summary_by_currency"))
        return tuple(result)

    def _options(self, symbol: str, raw: object, effective_at: datetime, observed_at: datetime) -> tuple[Observation, ...]:
        if not isinstance(raw, list): raise DeribitPublicUnavailable("SCHEMA_DRIFT")
        totals = {"C": Decimal("0"), "P": Decimal("0")}
        for item in raw:
            if not isinstance(item, Mapping): raise DeribitPublicUnavailable("SCHEMA_DRIFT")
            name = str(item.get("instrument_name") or "")
            kind = name.rsplit("-", 1)[-1]
            if kind in totals: totals[kind] += _decimal(item.get("open_interest"), "INVALID_OPTIONS")
        if totals["C"] <= 0 or totals["P"] <= 0: raise DeribitPublicUnavailable("OPTIONS_COVERAGE_INCOMPLETE")
        return (
            self._row(symbol=symbol, metric=CALL_OI, value=totals["C"], unit="contracts", effective_at=effective_at, observed_at=observed_at, endpoint="get_book_summary_by_currency"),
            self._row(symbol=symbol, metric=PUT_OI, value=totals["P"], unit="contracts", effective_at=effective_at, observed_at=observed_at, endpoint="get_book_summary_by_currency"),
            self._row(symbol=symbol, metric=PUT_CALL_OI_RATIO, value=totals["P"] / totals["C"], unit="ratio", effective_at=effective_at, observed_at=observed_at, endpoint="get_book_summary_by_currency"),
        )


__all__ = ["DeribitPublicClient", "DeribitPublicDerivativesCollector", "DeribitPublicUnavailable"]
