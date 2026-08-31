"""Source-attributed Binance USD-M futures history collector."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Protocol
from urllib.parse import urlencode

from .collectors import CollectorUnavailable
from .contracts import Observation
from .derivatives import ASSETS, DerivativeBackfillRequest, DerivativeCoverage, FUNDING_ANNUALIZED, OI_USD, PERPETUAL_PRICE_USD, TAKER_IMBALANCE
from .sources import source_for_code
from .transport import RequestsTransport, Transport


UTC = timezone.utc


class BinanceClient(Protocol):
    def get(self, path: str, params: Mapping[str, object]) -> object: ...


class BinanceUsdmDerivativesUnavailable(CollectorUnavailable):
    pass


class BinancePublicClient:
    base_url = "https://fapi.binance.com"

    def __init__(self, *, transport: Transport | None = None) -> None:
        self.transport = transport or RequestsTransport()

    def get(self, path: str, params: Mapping[str, object]) -> object:
        url = f"{self.base_url}{path}?{urlencode(params)}"
        response = self.transport.fetch(url, timeout_seconds=30, max_bytes=4_000_000)
        if response.status != 200 or response.url != url:
            raise BinanceUsdmDerivativesUnavailable("INVALID_RESPONSE")
        try:
            return json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BinanceUsdmDerivativesUnavailable("INVALID_RESPONSE") from exc


def _decimal(value: object, error: str, *, non_negative: bool = True) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise BinanceUsdmDerivativesUnavailable(error) from exc
    if not parsed.is_finite() or (non_negative and parsed < 0):
        raise BinanceUsdmDerivativesUnavailable(error)
    return parsed


def _timestamp(value: object) -> datetime:
    try:
        return datetime.fromtimestamp(int(str(value)) / 1000, UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    except (TypeError, ValueError, OSError) as exc:
        raise BinanceUsdmDerivativesUnavailable("INVALID_TIMESTAMP") from exc


class BinanceUsdmDerivativesCollector:
    source_code = "binance-usdm-derivatives"

    def __init__(self, *, client: BinanceClient | None = None) -> None:
        self.client = client or BinancePublicClient()
        self.source = source_for_code(self.source_code)

    def _observation(self, *, symbol: str, metric: str, value: Decimal, unit: str, effective_at: datetime, observed_at: datetime, endpoint: str, history_limited: bool = False) -> Observation:
        return Observation.create(
            source_code=self.source.code,
            source_url=f"{self.source.urls[0].rstrip('/')}{endpoint}", market=self.source.market,
            symbol=symbol, effective_at=effective_at, observed_at=observed_at,
            methodology_version=self.source.methodology_version,
            value={"metric": metric, "value": str(value), "unit": unit,
                   "dimensions": {"venue": "binance-usdm", "frequency": "daily", "historyLimited": history_limited}, "evidenceOnly": True},
            data_class="LIVE",
        )

    def backfill(self, request: DerivativeBackfillRequest) -> tuple[tuple[Observation, ...], tuple[DerivativeCoverage, ...]]:
        if request.source != self.source_code:
            raise ValueError("source mismatch")
        observed_at = request.end.astimezone(UTC)
        observations: list[Observation] = []
        coverage: list[DerivativeCoverage] = []
        for raw_symbol in request.symbols:
            symbol = raw_symbol.upper()
            funding = self._funding_rows(symbol, request, observed_at)
            price = self._price_rows(symbol, request, observed_at)
            limited = self._limited_rows(symbol, observed_at)
            observations.extend([*funding, *price, *limited])
            for metric, rows, history_limited in (
                (FUNDING_ANNUALIZED, funding, False), (PERPETUAL_PRICE_USD, price, False),
                (OI_USD, [row for row in limited if row.value["metric"] == OI_USD], True),
                (TAKER_IMBALANCE, [row for row in limited if row.value["metric"] == TAKER_IMBALANCE], True),
            ):
                if rows:
                    points = sorted(rows, key=lambda row: row.effective_at)
                    coverage.append(DerivativeCoverage(self.source_code, metric, symbol, points[0].effective_at, points[-1].effective_at, history_limited))
        return tuple(observations), tuple(coverage)

    def _funding_rows(self, symbol: str, request: DerivativeBackfillRequest, observed_at: datetime) -> list[Observation]:
        start, end = int(request.start.timestamp() * 1000), int(request.end.timestamp() * 1000)
        grouped: dict[datetime, list[Decimal]] = defaultdict(list)
        while start <= end:
            payload = self.client.get("/fapi/v1/fundingRate", {"symbol": f"{symbol}USDT", "startTime": start, "endTime": end, "limit": 1000})
            if not isinstance(payload, list): raise BinanceUsdmDerivativesUnavailable("SCHEMA_DRIFT")
            last_timestamp: int | None = None
            for item in payload:
                if not isinstance(item, Mapping): raise BinanceUsdmDerivativesUnavailable("SCHEMA_DRIFT")
                grouped[_timestamp(item.get("fundingTime"))].append(_decimal(item.get("fundingRate"), "INVALID_FUNDING", non_negative=False))
                last_timestamp = int(str(item.get("fundingTime")))
            if len(payload) < 1000 or last_timestamp is None: break
            start = last_timestamp + 1
        return [self._observation(symbol=symbol, metric=FUNDING_ANNUALIZED, value=sum(rates, Decimal("0")) * Decimal("365"), unit="return", effective_at=effective_at, observed_at=observed_at, endpoint="/fapi/v1/fundingRate") for effective_at, rates in sorted(grouped.items())]

    def _price_rows(self, symbol: str, request: DerivativeBackfillRequest, observed_at: datetime) -> list[Observation]:
        payload = self.client.get("/fapi/v1/klines", {"symbol": f"{symbol}USDT", "interval": "1d", "startTime": int(request.start.timestamp() * 1000), "endTime": int(request.end.timestamp() * 1000), "limit": 1500})
        if not isinstance(payload, list): raise BinanceUsdmDerivativesUnavailable("SCHEMA_DRIFT")
        rows = []
        for item in payload:
            if not isinstance(item, list) or len(item) < 5: raise BinanceUsdmDerivativesUnavailable("SCHEMA_DRIFT")
            rows.append(self._observation(symbol=symbol, metric=PERPETUAL_PRICE_USD, value=_decimal(item[4], "INVALID_PRICE"), unit="USD", effective_at=_timestamp(item[0]), observed_at=observed_at, endpoint="/fapi/v1/klines"))
        return rows

    def _limited_rows(self, symbol: str, observed_at: datetime) -> list[Observation]:
        result: list[Observation] = []
        oi = self.client.get("/futures/data/openInterestHist", {"symbol": f"{symbol}USDT", "period": "1d", "limit": 30})
        if not isinstance(oi, list): raise BinanceUsdmDerivativesUnavailable("SCHEMA_DRIFT")
        for item in oi:
            if not isinstance(item, Mapping): raise BinanceUsdmDerivativesUnavailable("SCHEMA_DRIFT")
            result.append(self._observation(symbol=symbol, metric=OI_USD, value=_decimal(item.get("sumOpenInterestValue"), "INVALID_OPEN_INTEREST"), unit="USD", effective_at=_timestamp(item.get("timestamp")), observed_at=observed_at, endpoint="/futures/data/openInterestHist", history_limited=True))
        taker = self.client.get("/futures/data/takerlongshortRatio", {"symbol": f"{symbol}USDT", "period": "1d", "limit": 30})
        if not isinstance(taker, list): raise BinanceUsdmDerivativesUnavailable("SCHEMA_DRIFT")
        for item in taker:
            if not isinstance(item, Mapping): raise BinanceUsdmDerivativesUnavailable("SCHEMA_DRIFT")
            ratio = _decimal(item.get("buySellRatio"), "INVALID_TAKER_RATIO")
            imbalance = (ratio - Decimal("1")) / (ratio + Decimal("1"))
            result.append(self._observation(symbol=symbol, metric=TAKER_IMBALANCE, value=imbalance, unit="ratio", effective_at=_timestamp(item.get("timestamp")), observed_at=observed_at, endpoint="/futures/data/takerlongshortRatio", history_limited=True))
        return result

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None: raise ValueError("as_of must be timezone-aware")
        end = as_of.astimezone(UTC)
        rows, _coverage = self.backfill(DerivativeBackfillRequest(self.source_code, ASSETS, end - timedelta(days=7), end))
        return rows


__all__ = ["BinancePublicClient", "BinanceUsdmDerivativesCollector", "BinanceUsdmDerivativesUnavailable"]
