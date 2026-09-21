"""Vietnamese equity OHLCV with VNDIRECT primary and Yahoo fallback."""

from __future__ import annotations

from datetime import date, datetime, time as day_time, timedelta, timezone
import os
import re
from typing import Any, Callable, Dict, List, Optional, Sequence
from zoneinfo import ZoneInfo

from app.data_sources.base import BaseDataSource
from app.data_sources.vn_market_providers import (
    VndirectProvider,
    VietnamMarketDataSettings,
    VietnamPriceProvider,
    YahooVietnamProvider,
)
from app.utils.cache import CacheManager
from app.utils.logger import get_logger
from app.services.vietnam_market_history import (
    VietnamDailyPriceRepository,
    normalize_price_mode,
    select_vietnam_daily_bars,
)


logger = get_logger(__name__)
_VN_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
_VN_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")
_TIMEFRAME_MINUTES = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1H": 60, "4H": 240}


def normalize_vietnam_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    for suffix in (".VN", ":VN", "@VN"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    if not _VN_SYMBOL_RE.fullmatch(value):
        raise ValueError(f"Invalid Vietnamese stock symbol: {symbol}")
    return value


def _canonical_timeframe(value: str) -> str:
    aliases = {"1d": "1D", "D": "1D", "1day": "1D", "1h": "1H", "4h": "4H"}
    timeframe = aliases.get(str(value or "1D").strip(), str(value or "1D").strip())
    return timeframe if timeframe in {*_TIMEFRAME_MINUTES, "1D"} else ""


class VNStockDataSource(BaseDataSource):
    name = "VNStock/vndirect+yahoo"

    def __init__(
        self,
        *,
        providers: Sequence[VietnamPriceProvider] | None = None,
        cache: Any | None = None,
        now: Callable[[], datetime] | None = None,
        history_persist: Callable[..., None] | None = None,
    ) -> None:
        settings = VietnamMarketDataSettings.from_env()
        if providers is None:
            default_providers: list[VietnamPriceProvider] = [
                VndirectProvider(settings=settings),
                YahooVietnamProvider(timeout_seconds=settings.timeout_seconds),
            ]
            providers = default_providers
        self.providers = list(providers)
        self.cache = cache or CacheManager()
        self.now = now or (lambda: datetime.now(tz=_VN_ZONE))
        self.history_persist = history_persist or VietnamDailyPriceRepository.persist
        self.last_kline_provider = ""
        self.last_kline_attempts: tuple[str, ...] = ()
        self.last_price_mode = "raw"
        self.last_kline_quality: dict[str, Any] = {}

    def get_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None,
        after_time: Optional[int] = None,
        *,
        price_mode: str = "raw",
    ) -> List[Dict[str, Any]]:
        canonical = normalize_vietnam_symbol(symbol)
        mode = normalize_price_mode(price_mode)
        frame = _canonical_timeframe(timeframe)
        if not frame:
            return []
        if frame != "1D" and mode != "raw":
            raise ValueError("adjusted_vietnam_prices_require_daily_timeframe")
        max_rows = max(1, min(int(limit or 1), 3650))
        end = (
            datetime.fromtimestamp(int(before_time) - 1, tz=timezone.utc).astimezone(_VN_ZONE).date()
            if before_time else self.now().astimezone(_VN_ZONE).date()
        )
        start = (
            datetime.fromtimestamp(int(after_time), tz=timezone.utc).astimezone(_VN_ZONE).date()
            if after_time
            else end - timedelta(days=max_rows * (2 if frame == "1D" else 1) + 14)
        )
        if start > end:
            return []

        cache_key = f"vn-ohlcv:v3:{canonical}:{frame}:{mode}:{start}:{end}:{max_rows}:{before_time or 0}:{after_time or 0}"
        cached = self.cache.get(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get("bars"), list):
            self.last_kline_provider = str(cached.get("provider") or "")
            self.last_kline_attempts = tuple(cached.get("attempts") or (self.last_kline_provider,))
            self.last_price_mode = str(cached.get("price_mode") or mode)
            self.last_kline_quality = dict(cached.get("quality") or {})
            return cached["bars"]

        historical = bool(before_time or after_time)
        attempts: list[str] = []
        if frame == "1D" and mode != "raw":
            provider_results: list[tuple[str, list[dict[str, Any]]]] = []
            for provider in self.providers:
                attempts.append(provider.name)
                try:
                    bars = provider.fetch_ohlcv(canonical, frame, start, end, max_rows)
                except Exception as exc:
                    logger.debug("VN price provider %s failed for %s: %s", provider.name, canonical, exc)
                    continue
                bars = self.filter_and_limit(
                    bars, max_rows, before_time=before_time, after_time=after_time,
                    truncate=False,
                )
                if bars and (historical or self._is_fresh(bars[-1]["time"], frame)):
                    provider_results.append((provider.name, bars))
            selection = select_vietnam_daily_bars(provider_results, mode)
            bars = self.filter_and_limit(
                list(selection.bars), max_rows, before_time=before_time,
                after_time=after_time, truncate=after_time is None,
            )
            if not bars:
                self.last_kline_provider = ""
                self.last_kline_attempts = tuple(attempts)
                self.last_price_mode = mode
                self.last_kline_quality = {
                    "coverage": selection.coverage, "flags": list(selection.flags)
                }
                return []
            quality = {"coverage": selection.coverage, "flags": list(selection.flags)}
            self._remember_selection(
                cache_key=cache_key, canonical=canonical, mode=mode,
                provider=selection.provider, attempts=attempts, bars=bars,
                canonical_rows=list(selection.canonical_rows), quality=quality,
                timeframe=frame,
            )
            return bars

        for provider in self.providers:
            attempts.append(provider.name)
            try:
                bars = provider.fetch_ohlcv(canonical, frame, start, end, max_rows)
            except Exception as exc:
                logger.debug("VN price provider %s failed for %s: %s", provider.name, canonical, exc)
                continue
            bars = self.filter_and_limit(
                bars,
                max_rows,
                before_time=before_time,
                after_time=after_time,
                truncate=after_time is None,
            )
            if not bars or (not historical and not self._is_fresh(bars[-1]["time"], frame)):
                continue
            selection = select_vietnam_daily_bars([(provider.name, bars)], mode) if frame == "1D" else None
            selected_bars = list(selection.bars) if selection else bars
            quality = {
                "coverage": selection.coverage if selection else 1.0,
                "flags": list(selection.flags) if selection else [],
            }
            self._remember_selection(
                cache_key=cache_key, canonical=canonical, mode=mode,
                provider=provider.name, attempts=attempts, bars=selected_bars,
                canonical_rows=list(selection.canonical_rows) if selection else [],
                quality=quality, timeframe=frame,
            )
            return selected_bars

        self.last_kline_provider = ""
        self.last_kline_attempts = tuple(attempts)
        self.last_price_mode = mode
        self.last_kline_quality = {"coverage": 0.0, "flags": ["no_provider_bars"]}
        return []

    def _remember_selection(
        self, *, cache_key: str, canonical: str, mode: str, provider: str,
        attempts: list[str], bars: list[dict[str, Any]],
        canonical_rows: list[dict[str, Any]], quality: dict[str, Any], timeframe: str,
    ) -> None:
        self.last_kline_provider = provider
        self.last_kline_attempts = tuple(attempts)
        self.last_price_mode = mode
        self.last_kline_quality = quality
        self.cache.set(
            cache_key,
            {
                "provider": provider, "attempts": attempts, "bars": bars,
                "price_mode": mode, "quality": quality,
            },
            self._cache_ttl(timeframe),
        )
        if timeframe == "1D" and canonical_rows:
            try:
                self.history_persist(
                    symbol=canonical, price_mode=mode, provider=provider,
                    bars=canonical_rows, quality=quality,
                )
            except Exception as exc:
                logger.debug("VN daily history persistence failed for %s: %s", canonical, exc)

    def _is_fresh(self, timestamp: int, timeframe: str) -> bool:
        now = self.now().astimezone(_VN_ZONE)
        observed = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).astimezone(_VN_ZONE)
        if observed > now + timedelta(minutes=5):
            return False
        if timeframe == "1D":
            expected = now.date() if now.time() >= day_time(15, 15) else _previous_business_day(now.date())
            tolerance = max(1, int(os.getenv("VN_DAILY_MAX_STALENESS_DAYS", "10")))
            return observed.date() >= expected - timedelta(days=tolerance)
        minute_size = _TIMEFRAME_MINUTES[timeframe]
        in_session = now.weekday() < 5 and (
            day_time(9, 0) <= now.time() <= day_time(11, 30)
            or day_time(13, 0) <= now.time() <= day_time(15, 0)
        )
        if in_session:
            return now - observed <= timedelta(minutes=max(20, minute_size * 3))
        expected_day = (
            now.date()
            if now.weekday() < 5 and now.time() >= day_time(9, 0)
            else _previous_business_day(now.date())
        )
        return observed.date() >= expected_day

    @staticmethod
    def _cache_ttl(timeframe: str) -> int:
        return 300 if timeframe == "1D" else max(30, _TIMEFRAME_MINUTES[timeframe] * 30)

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        canonical = normalize_vietnam_symbol(symbol)
        bars = self.get_kline(canonical, "1D", 2)
        if not bars:
            return {"last": 0, "symbol": canonical}
        latest = bars[-1]
        previous = bars[-2]["close"] if len(bars) > 1 else latest["close"]
        change = latest["close"] - previous
        return {
            "last": latest["close"],
            "change": change,
            "changePercent": (change / previous * 100) if previous else 0,
            "high": latest["high"],
            "low": latest["low"],
            "open": latest["open"],
            "previousClose": previous,
            "symbol": canonical,
            "provider": self.last_kline_provider,
            "timeframe": "1D",
            "time": latest.get("time"),
        }

    def probe_daily_provider_health(self, symbol: str) -> list[dict[str, Any]]:
        """Probe each configured free feed once for operator health, not user traffic."""

        canonical = normalize_vietnam_symbol(symbol)
        end = self.now().astimezone(_VN_ZONE).date()
        start = end - timedelta(days=14)
        outcomes: list[dict[str, Any]] = []
        for provider in self.providers:
            try:
                bars = provider.fetch_ohlcv(canonical, "1D", start, end, 5)
            except Exception as exc:
                outcomes.append({
                    "provider": provider.name,
                    "status": "unavailable",
                    "error": _provider_error_code(exc),
                })
                continue
            fresh = bool(bars) and self._is_fresh(int(bars[-1]["time"]), "1D")
            outcomes.append({
                "provider": provider.name,
                "status": "ok" if fresh else ("stale" if bars else "empty"),
                "bars": len(bars or []),
            })
        return outcomes


def _previous_business_day(value: date) -> date:
    candidate = value - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _provider_error_code(error: Exception) -> str:
    """Bound operational error grouping; do not store hostnames or exception text."""

    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return f"http_{status_code}"
    name = type(error).__name__.lower()
    if "timeout" in name:
        return "timeout"
    if "connection" in name or "network" in name:
        return "network"
    return "provider_error"


__all__ = ["VNStockDataSource", "normalize_vietnam_symbol"]
