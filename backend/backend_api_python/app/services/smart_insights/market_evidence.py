"""LIVE market-bar evidence for assets explicitly saved to AI watchlists."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol

from .collectors import CollectorUnavailable
from .contracts import DataClass, Observation
from .sources import source_for_code


UTC = timezone.utc
SOURCE_CODE = "datavest-market-bars"
_DAILY_BAR_COUNT = 21


class KlineClient(Protocol):
    def get_kline(self, market: str, symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]: ...


_INSTRUMENTS: dict[str, tuple[str, str, str]] = {
    "CRYPTO": ("Crypto", "crypto", ""),
    "VNSTOCK": ("VNStock", "vn", ""),
    "FOREX": ("Forex", "gold", "XAU"),
}


def _identity(item: Mapping[str, object]) -> tuple[str, str, str] | None:
    raw_market = str(item.get("market") or "").strip().upper()
    mapping = _INSTRUMENTS.get(raw_market)
    raw_symbol = str(item.get("symbol") or "").strip().upper()
    if not mapping or not raw_symbol:
        return None
    requested_market, insight_market, forced_symbol = mapping
    if requested_market == "Crypto":
        compact_symbol = raw_symbol.split("/", 1)[0]
    elif requested_market == "Forex":
        compact_symbol = forced_symbol if raw_symbol.replace("/", "") in {"XAU", "XAUUSD", "GOLD"} else ""
    else:
        compact_symbol = raw_symbol
    return (requested_market, raw_symbol, compact_symbol and f"{insight_market}:{compact_symbol}")


def _usable_bars(rows: Sequence[Mapping[str, object]]) -> list[tuple[int, float]]:
    normalized: list[tuple[int, float]] = []
    seen_times: set[int] = set()
    for row in rows:
        try:
            timestamp = int(row.get("time") or 0)
            close = float(row.get("close") or 0)
        except (TypeError, ValueError):
            continue
        if timestamp <= 0 or timestamp in seen_times or not math.isfinite(close) or close <= 0:
            continue
        seen_times.add(timestamp)
        normalized.append((timestamp, close))
    return sorted(normalized, key=lambda item: item[0])


class WatchlistMarketEvidenceCollector:
    """Persist derived daily-bar facts only when the public adapter returns real bars.

    This collector intentionally produces facts, not a directional recommendation.
    The snapshot pipeline keeps its ``EVIDENCE_ONLY`` stance until a separately
    validated directional model is introduced.
    """

    source_code = SOURCE_CODE

    def __init__(
        self,
        *,
        kline_service: KlineClient | None = None,
        instruments_loader: Callable[[], Sequence[Mapping[str, object]]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if kline_service is None:
            from app.services.kline import KlineService

            kline_service = KlineService()
        if instruments_loader is None:
            from .repository import SmartInsightsRepository

            instruments_loader = SmartInsightsRepository().list_distinct_supported_watchlist_instruments
        self.kline_service = kline_service
        self.instruments_loader = instruments_loader
        self.clock = clock or (lambda: datetime.now(UTC))
        self.source = source_for_code(self.source_code)

    def collect(self) -> tuple[Observation, ...]:
        current_time = self.clock()
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        observed_at = current_time.astimezone(UTC)
        identities = sorted(
            {
                identity
                for item in self.instruments_loader()
                if isinstance(item, Mapping)
                for identity in [_identity(item)]
                if identity and identity[2]
            }
        )
        observations: list[Observation] = []
        for requested_market, requested_symbol, compact_key in identities:
            insight_market, symbol = compact_key.split(":", 1)
            try:
                bars = _usable_bars(
                    self.kline_service.get_kline(
                        requested_market, requested_symbol, "1D", _DAILY_BAR_COUNT
                    )
                )
            except Exception:
                continue
            if len(bars) < _DAILY_BAR_COUNT:
                continue
            latest_time, latest_close = bars[-1]
            _, previous_close = bars[-2]
            _, close_20d_ago = bars[-_DAILY_BAR_COUNT]
            effective_at = datetime.fromtimestamp(latest_time, tz=UTC)
            common = {
                "requestedMarket": requested_market,
                "requestedSymbol": requested_symbol,
                "timeframe": "1D",
                "barCount": len(bars),
                "evidenceOnly": True,
            }
            metrics = (
                ("market.price.close", latest_close, "price"),
                ("market.return_1d_pct", ((latest_close / previous_close) - 1) * 100, "percent"),
                ("market.return_20d_pct", ((latest_close / close_20d_ago) - 1) * 100, "percent"),
            )
            for metric, value, unit in metrics:
                observations.append(
                    Observation.create(
                        source_code=self.source.code,
                        source_url=self.source.urls[0],
                        market=insight_market,
                        symbol=symbol,
                        effective_at=effective_at,
                        observed_at=observed_at,
                        methodology_version=self.source.methodology_version,
                        value={"metric": metric, "value": value, "unit": unit, **common},
                        data_class=DataClass.LIVE,
                    )
                )
        if not observations:
            raise CollectorUnavailable("NO_SUPPORTED_WATCHLIST_BARS")
        return tuple(observations)


__all__ = ["SOURCE_CODE", "WatchlistMarketEvidenceCollector"]
