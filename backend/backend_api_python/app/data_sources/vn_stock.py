"""Read-only Vietnamese equity data source backed by the public KB feed."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
import re
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from app.data_sources.base import BaseDataSource
from app.utils.logger import get_logger

logger = get_logger(__name__)

_VN_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
_VN_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def normalize_vietnam_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    for suffix in (".VN", ":VN", "@VN"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    if not _VN_SYMBOL_RE.fullmatch(value):
        raise ValueError(f"Invalid Vietnamese stock symbol: {symbol}")
    return value


class VNStockDataSource(BaseDataSource):
    """Vietnamese stocks and indexes through KB Securities' public endpoint."""

    name = "VNStock/kbs-public"

    def __init__(self) -> None:
        self.last_kline_provider = ""

    @staticmethod
    def _request_url(symbol: str, start: date, end: date) -> str:
        kind = "index" if symbol in {"VNINDEX", "VN30"} else "stocks"
        return (
            "https://kbbuddywts.kbsec.com.vn/iis-server/investment/"
            f"{kind}/{symbol}/data_day"
            f"?sdate={start.strftime('%d-%m-%Y')}&edate={end.strftime('%d-%m-%Y')}"
        )

    def _fetch_daily(self, symbol: str, start: date, end: date) -> List[Dict[str, Any]]:
        url = self._request_url(symbol, start, end)
        response = requests.get(
            url,
            timeout=20,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; DataVest-MarketData/1.0)",
            },
        )
        response.raise_for_status()
        payload = response.json()
        records = payload.get("data_day") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise ValueError("VN provider returned an invalid schema")

        bars: List[Dict[str, Any]] = []
        seen_days = set()
        for record in records:
            if not isinstance(record, dict):
                continue
            try:
                timestamp = datetime.strptime(str(record["t"]), "%Y-%m-%d %H:%M").replace(tzinfo=_VN_ZONE)
                local_day = timestamp.date()
                open_price, high, low, close = (float(record[key]) for key in ("o", "h", "l", "c"))
                volume = float(record.get("v") or 0)
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            if local_day in seen_days or not start <= local_day <= end:
                continue
            if any(not math.isfinite(value) or value <= 0 for value in (open_price, high, low, close)):
                continue
            if not math.isfinite(volume) or volume < 0:
                continue
            if not (low <= open_price <= high and low <= close <= high):
                continue
            seen_days.add(local_day)
            bars.append({
                "time": int(timestamp.astimezone(timezone.utc).timestamp()),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            })
        bars.sort(key=lambda item: item["time"])
        return bars

    def get_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None,
        after_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if str(timeframe or "1D").strip() not in {"1D", "1d", "D", "1day"}:
            return []
        canonical = normalize_vietnam_symbol(symbol)
        max_rows = max(1, min(int(limit or 1), 3650))
        end = (
            datetime.fromtimestamp(int(before_time) - 1, tz=timezone.utc).astimezone(_VN_ZONE).date()
            if before_time
            else datetime.now(tz=_VN_ZONE).date()
        )
        start = (
            datetime.fromtimestamp(int(after_time), tz=timezone.utc).astimezone(_VN_ZONE).date()
            if after_time
            else end - timedelta(days=max_rows * 2 + 14)
        )
        if start > end:
            return []
        try:
            bars = self._fetch_daily(canonical, start, end)
        except Exception as exc:
            self.last_kline_provider = ""
            logger.debug("VNStock provider failed for %s: %s", canonical, exc)
            return []
        self.last_kline_provider = "kbs-public" if bars else ""
        return self.filter_and_limit(
            bars,
            max_rows,
            before_time=before_time,
            after_time=after_time,
            truncate=after_time is None,
        )

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        bars = self.get_kline(symbol, "1D", 2)
        if not bars:
            return {"last": 0, "symbol": normalize_vietnam_symbol(symbol)}
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
            "symbol": normalize_vietnam_symbol(symbol),
        }
