"""Watchlist scoping for Smart Insights read models.

The persisted watchlist uses provider-specific pair formats while imported
briefings use compact symbols. Normalize both sides before filtering so an
empty watchlist never accidentally exposes the user's full production brief.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def _pair_key(market: Any, symbol: Any) -> str | None:
    market_name = str(market or "").strip().lower()
    raw_symbol = str(symbol or "").strip().upper()
    if not market_name or not raw_symbol:
        return None
    compact = re.sub(r"[ /_-]+", "", raw_symbol)
    if market_name in {"crypto", "cryptocurrency"}:
        base = compact
        for quote in ("USDT", "USDC", "USD", "BUSD", "BTC", "ETH"):
            if base.endswith(quote) and len(base) > len(quote):
                base = base[: -len(quote)]
                break
        return f"crypto:{base}"
    if market_name in {"forex", "fx", "gold", "xau", "commodity"}:
        return "gold:XAU" if compact in {"XAU", "XAUUSD", "GOLD"} else f"gold:{compact}"
    if market_name in {"vietnam", "vn", "vnstock", "equity"}:
        return f"vn:{compact}"
    if market_name in {"us", "usstock", "usstocks"}:
        return f"us:{compact}"
    return f"{market_name}:{compact}"


def opinion_key(opinion: Mapping[str, Any]) -> str | None:
    return _pair_key(opinion.get("market"), opinion.get("symbol"))


def filter_opinions_to_watchlist(
    opinions: list[Mapping[str, Any]], watchlist_pairs: list[Mapping[str, Any]] | None
) -> list[Mapping[str, Any]]:
    """Filter opinions by the authenticated user's explicit watchlist.

    ``None`` means the caller did not request scoping and is retained for
    repository compatibility. An empty list is a deliberate empty watchlist.
    """
    if watchlist_pairs is None:
        return list(opinions)
    keys = {
        key
        for pair in watchlist_pairs
        if isinstance(pair, Mapping)
        for key in [_pair_key(pair.get("market"), pair.get("symbol"))]
        if key
    }
    return [opinion for opinion in opinions if opinion_key(opinion) in keys]


__all__ = ["filter_opinions_to_watchlist", "opinion_key"]
