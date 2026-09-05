"""Explicit DataVest-to-TradingAgents instrument mapping."""

from __future__ import annotations

import re


class InstrumentResolutionError(ValueError):
    """Raised when a DataVest market/symbol cannot map to an upstream identity."""


_CRYPTO_PAIR = re.compile(r"^([A-Z0-9]{2,20})/(USDT|USD)$")
_CRYPTO_USD = re.compile(r"^([A-Z0-9]{2,20})-USD$")
_VN_SYMBOL = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


def resolve_instrument(market: str, symbol: str) -> tuple[str, str]:
    """Resolve a supported DataVest symbol without silently choosing a market."""

    normalized_market = market.strip().casefold() if isinstance(market, str) else ""
    normalized_symbol = symbol.strip().upper() if isinstance(symbol, str) else ""

    if normalized_market == "crypto":
        pair = _CRYPTO_PAIR.fullmatch(normalized_symbol)
        if pair:
            return f"{pair.group(1)}-USD", "crypto"
        if _CRYPTO_USD.fullmatch(normalized_symbol):
            return normalized_symbol, "crypto"
    elif normalized_market == "vnstock" and _VN_SYMBOL.fullmatch(normalized_symbol):
        return f"{normalized_symbol}.VN", "stock"
    elif normalized_market == "gold" and normalized_symbol in {"XAU", "XAUUSD"}:
        return "XAUUSD", "stock"

    raise InstrumentResolutionError(f"Unsupported DataVest instrument: {market!r} / {symbol!r}")
