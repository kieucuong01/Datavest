"""Product market scope shared by all active DataVest market flows."""

from __future__ import annotations

from typing import Any


SUPPORTED_MARKET_ORDER = ("USStock", "VNStock", "Crypto", "Forex")
SUPPORTED_MARKETS = frozenset(SUPPORTED_MARKET_ORDER)
# Keep USStock in the internal contract for a controlled future re-enable. The
# current DataVest product surface is intentionally limited to VN, crypto and
# gold/XAU.
DEFAULT_VISIBLE_MARKET_ORDER = ("VNStock", "Crypto", "Forex")
DEFAULT_VISIBLE_MARKETS = frozenset(DEFAULT_VISIBLE_MARKET_ORDER)


class UnsupportedSupportedMarketError(ValueError):
    """Raised when a market is outside the DataVest product scope."""


def _market_key(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")


_MARKET_ALIASES = {
    "us": "USStock",
    "usstock": "USStock",
    "usstocks": "USStock",
    "stock": "USStock",
    "stocks": "USStock",
    "equity": "USStock",
    "equities": "USStock",
    "vn": "VNStock",
    "vietnam": "VNStock",
    "vnstock": "VNStock",
    "vietnamstock": "VNStock",
    "crypto": "Crypto",
    "cryptocurrency": "Crypto",
    "forex": "Forex",
    "fx": "Forex",
    "gold": "Forex",
    "xau": "Forex",
}

_GOLD_SYMBOL_ALIASES = frozenset({"XAU", "XAUUSD", "GOLD"})


def normalize_supported_market(value: Any) -> str:
    raw = str(value or "").strip()
    market = _MARKET_ALIASES.get(_market_key(raw), raw)
    if market not in SUPPORTED_MARKETS:
        raise UnsupportedSupportedMarketError(f"Unsupported market '{raw}'")
    return market


def canonicalize_supported_symbol(market: Any, symbol: Any) -> str:
    canonical_market = normalize_supported_market(market)
    raw_symbol = str(symbol or "").strip().upper()
    compact_symbol = raw_symbol.replace(" ", "").replace("/", "").replace("-", "")
    if canonical_market == "Forex":
        if compact_symbol not in _GOLD_SYMBOL_ALIASES:
            raise UnsupportedSupportedMarketError(
                "Only Gold/XAU is supported in the Forex provider namespace"
            )
        return "XAUUSD"
    if not raw_symbol:
        raise ValueError("Empty symbol")
    return raw_symbol


def is_supported_market(value: Any) -> bool:
    try:
        normalize_supported_market(value)
    except UnsupportedSupportedMarketError:
        return False
    return True
