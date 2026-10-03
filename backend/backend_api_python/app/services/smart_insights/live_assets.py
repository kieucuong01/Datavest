"""Source-backed live asset strip for the Smart Insights workspace."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.data_sources.vn_stock import expected_vietnam_daily_date
from app.services.market.quotes import get_price_map


LIVE_ASSET_CATALOG: tuple[dict[str, str], ...] = (
    {"displaySymbol": "BTC", "market": "Crypto", "symbol": "BTC/USDT"},
    {"displaySymbol": "ETH", "market": "Crypto", "symbol": "ETH/USDT"},
    {"displaySymbol": "SOL", "market": "Crypto", "symbol": "SOL/USDT"},
    {"displaySymbol": "XRP", "market": "Crypto", "symbol": "XRP/USDT"},
    {"displaySymbol": "LINK", "market": "Crypto", "symbol": "LINK/USDT"},
    {"displaySymbol": "VNINDEX", "market": "VNStock", "symbol": "VNINDEX"},
    {"displaySymbol": "VN30", "market": "VNStock", "symbol": "VN30"},
    {"displaySymbol": "XAU", "market": "Forex", "symbol": "XAUUSD"},
)
_VN_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _number(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0


def get_live_asset_snapshot(
    *,
    quote_fetcher: Callable[..., list[dict[str, Any]]] = get_price_map,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Fetch the fixed live strip without manufacturing missing prices."""
    quotes = quote_fetcher(list(LIVE_ASSET_CATALOG), timeout_sec=12)
    timestamp = fetched_at or datetime.now(timezone.utc).isoformat()
    retrieved = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=timezone.utc)
    indexed = {
        (row.get("market"), row.get("symbol")): row
        for row in quotes
        if isinstance(row, dict)
    }
    assets: list[dict[str, Any]] = []
    for item in LIVE_ASSET_CATALOG:
        quote = indexed.get((item["market"], item["symbol"]), {})
        price = _number(quote.get("price"))
        stale = bool(quote.get("stale"))
        timeframe = str(quote.get("timeframe") or "") if item["market"] == "VNStock" else ""
        try:
            observed = datetime.fromtimestamp(int(quote["time"]), tz=timezone.utc)
            observed_at = observed.isoformat()
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            observed = None
            observed_at = None
        is_vietnam = item["market"] == "VNStock"
        trade_date = observed.astimezone(_VN_ZONE).date().isoformat() if is_vietnam and observed else None
        if is_vietnam and (not observed or not quote.get("source") or not timeframe):
            price = 0
        old_session = bool(
            is_vietnam and observed and (
                observed > retrieved + timedelta(minutes=5)
                or observed.astimezone(_VN_ZONE).date() < expected_vietnam_daily_date(retrieved)
            )
        )
        assets.append(
            {
                **item,
                "price": price,
                "change": _number(quote.get("change")),
                "changePercent": _number(quote.get("changePercent")),
                "source": str(quote.get("source") or ""),
                "sourceExchangeId": str(quote.get("source_exchange_id") or ""),
                "sourceMarketType": str(quote.get("source_market_type") or ""),
                "cached": bool(quote.get("cached")),
                "stale": stale,
                "timeframe": timeframe,
                "observedAt": observed_at,
                "tradeDate": trade_date,
                "retrievedAt": timestamp if is_vietnam else None,
                "status": (
                    "STALE"
                    if price > 0 and (stale or old_session)
                    else "DAILY"
                    if price > 0 and is_vietnam and timeframe == "1D"
                    else "DELAYED"
                    if price > 0 and is_vietnam
                    else "LIVE"
                    if price > 0
                    else "UNAVAILABLE"
                ),
            }
        )
    return {"fetchedAt": timestamp, "assets": assets}


__all__ = ["LIVE_ASSET_CATALOG", "get_live_asset_snapshot"]
