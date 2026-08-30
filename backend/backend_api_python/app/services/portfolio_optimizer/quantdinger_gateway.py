"""Read-only QuantDinger market-data adapter for optimizer inputs."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import json
import math
import re
from zoneinfo import ZoneInfo

from app.data_sources import DataSourceFactory
from app.services.smart_insights.transport import RequestsTransport, Transport

from .market_data import Instrument, PriceSeries, series_checksum


def _unix(day: date, *, end: bool = False) -> int:
    clock = time.max if end else time.min
    return int(datetime.combine(day, clock, tzinfo=timezone.utc).timestamp())


class QuantDingerOptimizerGateway:
    """Fetch fresh daily data while preserving the provider that actually won fallback."""

    def __init__(
        self,
        *,
        vn_transport: Transport | None = None,
    ) -> None:
        self.vn_transport = vn_transport or RequestsTransport()

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
        instrument_kind = "index" if is_index else "stocks"
        request_url = (
            "https://kbbuddywts.kbsec.com.vn/iis-server/investment/"
            f"{instrument_kind}/{symbol}/data_day"
            f"?sdate={start.strftime('%d-%m-%Y')}&edate={end.strftime('%d-%m-%Y')}"
        )
        try:
            response = self.vn_transport.fetch(
                request_url,
                timeout_seconds=20,
                max_bytes=5_000_000,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (compatible; DataVest-MarketData/1.0)",
                },
            )
        except Exception as exc:
            raise ValueError("vn_market_data_unavailable: provider_request_failed") from exc
        if response.status != 200 or response.url != request_url:
            raise ValueError("vn_market_data_unavailable: provider_request_failed")
        try:
            payload = json.loads(response.body)
            records = payload["data_day"]
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("vn_market_data_unavailable: invalid_schema") from exc

        if not isinstance(records, list):
            raise ValueError("vn_market_data_unavailable: invalid_schema")
        if not records:
            raise ValueError("vn_market_data_unavailable: no_bars")

        required = {"t", "o", "h", "l", "c", "v"}
        local_zone = ZoneInfo("Asia/Ho_Chi_Minh")
        rows: list[tuple[int, float]] = []
        seen_local_days: set[date] = set()
        try:
            for record in records:
                if not isinstance(record, dict) or not required <= record.keys():
                    raise ValueError("invalid record")
                timestamp = datetime.strptime(str(record["t"]), "%Y-%m-%d %H:%M").replace(
                    tzinfo=local_zone
                )
                local_day = timestamp.astimezone(local_zone).date()

                prices = tuple(float(record[field]) for field in ("o", "h", "l", "c"))
                if any(not math.isfinite(value) or value <= 0 for value in prices):
                    raise ValueError("invalid price")
                volume = float(record["v"])
                if not math.isfinite(volume) or volume < 0:
                    raise ValueError("invalid volume")
                open_price, high_price, low_price, close_price = prices
                if not (
                    low_price <= open_price <= high_price
                    and low_price <= close_price <= high_price
                ):
                    raise ValueError("invalid OHLC ordering")
                if not start <= local_day <= end:
                    continue

                unix_time = int(timestamp.astimezone(timezone.utc).timestamp())
                if local_day in seen_local_days:
                    raise ValueError("duplicate local trading day")
                seen_local_days.add(local_day)
                rows.append((unix_time, close_price))
        except (ArithmeticError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("vn_market_data_unavailable: invalid_schema") from exc

        if not rows:
            raise ValueError("vn_market_data_unavailable: no_bars")
        rows.sort(key=lambda item: item[0])
        timestamps = tuple(item[0] for item in rows)
        closes = tuple(item[1] for item in rows)
        provider = "kbs-public"
        days = (end - start).days + 1
        expected = sum(
            1
            for offset in range(days)
            if date.fromordinal(start.toordinal() + offset).weekday() < 5
        )
        return PriceSeries(
            market="VNStock",
            symbol=symbol,
            currency=currency,
            timestamps=timestamps,
            closes=closes,
            provider=provider,
            fallback_chain=(provider,),
            coverage=min(1.0, len(rows) / max(expected, 1)),
            checksum=series_checksum(
                provider=provider, timestamps=timestamps, closes=closes
            ),
            data_class="LIVE",
            price_unit="INDEX_POINTS" if is_index else "VND",
            mark_to_market_supported=not is_index,
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
