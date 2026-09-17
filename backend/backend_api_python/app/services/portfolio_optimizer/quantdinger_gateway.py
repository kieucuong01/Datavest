"""Read-only QuantDinger market-data adapter for optimizer inputs."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import math
import os
import re
from typing import Callable

from app.data_sources import DataSourceFactory

from .market_data import Instrument, PriceSeries, series_checksum


def _unix(day: date, *, end: bool = False) -> int:
    clock = time.max if end else time.min
    return int(datetime.combine(day, clock, tzinfo=timezone.utc).timestamp())


class QuantDingerOptimizerGateway:
    """Fetch fresh daily data while preserving the provider that actually won fallback."""

    def __init__(
        self,
        *,
        vn_source_factory: Callable[[], object] | None = None,
    ) -> None:
        if vn_source_factory is None:
            from app.data_sources.vn_stock import VNStockDataSource

            vn_source_factory = VNStockDataSource
        self.vn_source_factory = vn_source_factory

    @staticmethod
    def _provider(source) -> str:
        explicit = str(getattr(source, "last_kline_provider", "") or "").strip()
        if explicit:
            return explicit
        exchange = getattr(source, "exchange", None)
        promoted = str(getattr(source, "_preferred_public_exchange_id", "") or "").strip()
        if promoted:
            return f"ccxt:{promoted}"
        exchange_id = str(getattr(exchange, "id", "") or "").strip()
        return f"ccxt:{exchange_id}" if exchange_id else ""

    def _fetch_vn(
        self,
        *,
        symbol: str,
        currency: str,
        start: date,
        end: date,
    ) -> PriceSeries:
        if end < start:
            raise ValueError("vn_market_data_unavailable: invalid_date_range")
        if not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", symbol):
            raise ValueError("vn_market_data_unavailable: invalid_symbol")
        if currency != "VND":
            raise ValueError("vn_market_data_unavailable: invalid_currency")
        is_index = symbol in {"VNINDEX", "VN30"}
        days = (end - start).days + 1
        limit = min(3_650, max(31, days + 16))
        source = self.vn_source_factory()
        try:
            bars = source.get_kline(
                symbol,
                "1D",
                limit,
                before_time=_unix(end, end=True) + 1,
                after_time=_unix(start),
                price_mode="total_return",
            )
        except Exception as exc:
            raise ValueError("vn_market_data_unavailable: provider_request_failed") from exc
        if not bars:
            raise ValueError("vn_market_data_unavailable: no_bars")

        rows: list[tuple[int, float]] = []
        seen_timestamps: set[int] = set()
        try:
            for record in bars:
                timestamp = int(record["time"])
                close_price = float(record["close"])
                if not math.isfinite(close_price) or close_price <= 0:
                    raise ValueError("invalid close")
                if not _unix(start) <= timestamp <= _unix(end, end=True):
                    continue
                if timestamp in seen_timestamps:
                    raise ValueError("duplicate timestamp")
                seen_timestamps.add(timestamp)
                rows.append((timestamp, close_price))
        except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("vn_market_data_unavailable: invalid_schema") from exc

        if not rows:
            raise ValueError("vn_market_data_unavailable: no_bars")
        rows.sort(key=lambda item: item[0])
        timestamps = tuple(item[0] for item in rows)
        closes = tuple(item[1] for item in rows)
        provider = str(getattr(source, "last_kline_provider", "") or "").strip()
        if not provider:
            raise ValueError("vn_market_data_unavailable: provider_unknown")
        attempts = tuple(str(value) for value in (getattr(source, "last_kline_attempts", ()) or ()) if value)
        fallback_chain = attempts or (provider,)
        expected = sum(
            1
            for offset in range(days)
            if date.fromordinal(start.toordinal() + offset).weekday() < 5
        )
        computed_coverage = min(1.0, len(rows) / max(expected, 1))
        source_quality = getattr(source, "last_kline_quality", {}) or {}
        coverage = float(source_quality.get("coverage", computed_coverage))
        try:
            minimum_coverage = float(os.getenv("VN_OPTIMIZER_MIN_COVERAGE", "0.90"))
        except ValueError:
            minimum_coverage = 0.90
        if coverage < max(0.0, min(1.0, minimum_coverage)):
            raise ValueError("vn_market_data_unavailable: insufficient_coverage")
        quality_flags = tuple(str(value) for value in source_quality.get("flags", ()) if value)
        price_mode = str(getattr(source, "last_price_mode", "") or "total_return")
        return PriceSeries(
            market="VNStock",
            symbol=symbol,
            currency=currency,
            timestamps=timestamps,
            closes=closes,
            provider=provider,
            fallback_chain=fallback_chain,
            coverage=coverage,
            checksum=series_checksum(
                provider=provider, timestamps=timestamps, closes=closes
            ),
            data_class="LIVE",
            price_unit="INDEX_POINTS" if is_index else "VND",
            mark_to_market_supported=not is_index,
            price_mode=price_mode,
            quality_flags=quality_flags,
        )

    def _fetch(
        self,
        *,
        market: str,
        symbol: str,
        currency: str,
        start_date: str,
        end_date: str,
        exchange_id: str = "",
        market_type: str = "",
    ) -> PriceSeries:
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError as exc:
            if market == "VNStock":
                raise ValueError("vn_market_data_unavailable: invalid_date_range") from exc
            raise
        days = (end - start).days + 1
        if market == "VNStock":
            return self._fetch_vn(
                symbol=symbol,
                currency=currency,
                start=start,
                end=end,
            )
        normalized = DataSourceFactory.normalize_market(market)
        source = DataSourceFactory._create_source(normalized)
        if normalized == "Crypto" and (exchange_id or market_type):
            from app.data_sources.crypto import CryptoDataSource

            source = CryptoDataSource.for_public_market(
                market_type or "spot", preferred_exchange_id=exchange_id
            )
        limit = min(3_650, max(31, days + 16))
        bars = source.get_kline(
            symbol,
            "1D",
            limit,
            before_time=_unix(end, end=True) + 1,
            after_time=_unix(start),
        )
        provider = self._provider(source)
        if not bars or not provider:
            raise ValueError("optimizer_market_data_unavailable")
        rows = sorted(
            (
                (int(item["time"]), float(item["close"]))
                for item in bars
                if _unix(start) <= int(item.get("time") or 0) <= _unix(end, end=True)
            ),
            key=lambda item: item[0],
        )
        timestamps = tuple(item[0] for item in rows)
        closes = tuple(item[1] for item in rows)
        expected = days if normalized == "Crypto" else sum(
            1 for offset in range(days) if date.fromordinal(start.toordinal() + offset).weekday() < 5
        )
        coverage = min(1.0, len(rows) / max(expected, 1))
        requested_provider = f"ccxt:{exchange_id}" if exchange_id else provider
        chain = (requested_provider,) if requested_provider == provider else (requested_provider, provider)
        return PriceSeries(
            market=market,
            symbol=symbol,
            currency=currency,
            timestamps=timestamps,
            closes=closes,
            provider=provider,
            fallback_chain=chain,
            coverage=coverage,
            checksum=series_checksum(provider=provider, timestamps=timestamps, closes=closes),
            data_class="LIVE",
        )

    def fetch_daily(self, instrument: Instrument, *, start_date: str, end_date: str) -> PriceSeries:
        return self._fetch(
            market=instrument.market,
            symbol=instrument.symbol,
            currency=instrument.currency,
            start_date=start_date,
            end_date=end_date,
            exchange_id=instrument.exchange_id,
            market_type=instrument.market_type,
        )

    def fetch_fx(
        self,
        source_currency: str,
        target_currency: str,
        *,
        start_date: str,
        end_date: str,
    ) -> PriceSeries | None:
        if source_currency == target_currency:
            return None
        try:
            return self._fetch(
                market="Forex",
                symbol=f"{source_currency}{target_currency}",
                currency=target_currency,
                start_date=start_date,
                end_date=end_date,
            )
        except (ValueError, RuntimeError):
            return None


__all__ = ["QuantDingerOptimizerGateway"]
