"""
Detect (market_category, symbol) from a free-form user prompt for the AI
trading-bot recommender.

Used by app/routes/strategy.py::ai_generate_strategy (intent='bot_recommend')
so the LLM can be fed real K-line data for the symbol the user mentioned.
Previously this lived inline in the route as a 24-entry crypto-only map,
which meant XAU / EUR/USD / TSLA fell through and the LLM had to hallucinate
price ranges for grid bots — leading to nonsense upper/lower bounds and
broken grids.

Design:
  - Try a multi-market lookup table first (covers the common, well-known
    tickers the LLM is most likely to be asked about).
  - Fall back to regex patterns scoped per market so we can detect things
    like "EUR/USD 走势" even if the pair isn't in the table.
  - Return the *normalized* symbol (BTC -> BTC/USDT, XAUUSD -> XAUUSD) so the
    kline data source receives the exact form it
    expects.

Public API:
  detect_market_and_symbol(prompt: str) -> Optional[Tuple[str, str]]
    where the first element is one of 'Crypto', 'USStock', 'VNStock', 'Forex' and the
    second is the canonical symbol for the kline data source.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple


# --- Lookup tables ----------------------------------------------------------
# Each map is keyed by tokens we expect to find in user prompts (case-folded
# to upper at lookup time). Values are the canonical symbol form the
# `KlineService.get_kline` data source expects for that market.
#
# Keep these moderate in size — the regex fallback handles the long tail.
# Order of precedence on duplicate keys: Forex > VNStock > USStock > Crypto. We don't
# have any duplicates today but the precedence is enforced in the loop below.

_CRYPTO_MAP = {
    "BTC": "BTC/USDT", "BITCOIN": "BTC/USDT",
    "ETH": "ETH/USDT", "ETHEREUM": "ETH/USDT",
    "SOL": "SOL/USDT", "SOLANA": "SOL/USDT",
    "BNB": "BNB/USDT",
    "XRP": "XRP/USDT", "RIPPLE": "XRP/USDT",
    "DOGE": "DOGE/USDT", "DOGECOIN": "DOGE/USDT",
    "ADA": "ADA/USDT", "CARDANO": "ADA/USDT",
    "AVAX": "AVAX/USDT", "AVALANCHE": "AVAX/USDT",
    "DOT": "DOT/USDT", "POLKADOT": "DOT/USDT",
    "MATIC": "MATIC/USDT", "POLYGON": "MATIC/USDT",
    "LINK": "LINK/USDT", "CHAINLINK": "LINK/USDT",
    "UNI": "UNI/USDT",
    "ATOM": "ATOM/USDT", "COSMOS": "ATOM/USDT",
    "LTC": "LTC/USDT", "LITECOIN": "LTC/USDT",
    "FIL": "FIL/USDT", "FILECOIN": "FIL/USDT",
    "ARB": "ARB/USDT", "ARBITRUM": "ARB/USDT",
    "OP": "OP/USDT", "OPTIMISM": "OP/USDT",
    "APT": "APT/USDT", "APTOS": "APT/USDT",
    "SUI": "SUI/USDT",
    "PEPE": "PEPE/USDT",
    "WIF": "WIF/USDT",
    "NEAR": "NEAR/USDT",
    "TRX": "TRX/USDT", "TRON": "TRX/USDT",
    "SHIB": "SHIB/USDT", "SHIBA": "SHIB/USDT",
    "TON": "TON/USDT",
    "INJ": "INJ/USDT",
    "ARB": "ARB/USDT",
}

# Gold is exposed through the Forex namespace for compatibility with the
# market contract. Generic FX pairs are intentionally unsupported.
_FOREX_MAP = {
    "XAU": "XAUUSD", "GOLD": "XAUUSD", "XAUUSD": "XAUUSD",
}

_VNSTOCK_MAP = {
    "FPT": "FPT", "VCB": "VCB", "HPG": "HPG", "VIC": "VIC",
    "VHM": "VHM", "VNM": "VNM", "SSI": "SSI", "MWG": "MWG",
    "VRE": "VRE", "MSN": "MSN", "GAS": "GAS", "BID": "BID",
    "CTG": "CTG", "TCB": "TCB", "ACB": "ACB", "MBB": "MBB",
    "VPB": "VPB",
}

# US stocks: a non-exhaustive list of the most-asked-about tickers. The
# regex fallback below catches any 1-5 letter all-caps token that isn't in
# the crypto / forex maps.
_USSTOCK_MAP = {
    "AAPL": "AAPL", "APPLE": "AAPL",
    "TSLA": "TSLA", "TESLA": "TSLA",
    "MSFT": "MSFT", "MICROSOFT": "MSFT",
    "NVDA": "NVDA", "NVIDIA": "NVDA",
    "GOOGL": "GOOGL", "GOOG": "GOOG", "GOOGLE": "GOOGL", "ALPHABET": "GOOGL",
    "AMZN": "AMZN", "AMAZON": "AMZN",
    "META": "META", "FB": "META", "FACEBOOK": "META",
    "NFLX": "NFLX", "NETFLIX": "NFLX",
    "AMD": "AMD",
    "COIN": "COIN", "COINBASE": "COIN",
    "PLTR": "PLTR", "PALANTIR": "PLTR",
    "MSTR": "MSTR",
    "SPY": "SPY", "QQQ": "QQQ", "IWM": "IWM", "DIA": "DIA",
    "BABA": "BABA", "ALIBABA": "BABA",
    "JPM": "JPM",
    "V": "V", "MA": "MA",
    "DIS": "DIS", "DISNEY": "DIS",
    "BA": "BA", "BOEING": "BA",
    "F": "F", "FORD": "F",
    "GM": "GM",
    "INTC": "INTC", "INTEL": "INTC",
    "ORCL": "ORCL", "ORACLE": "ORCL",
    "CRM": "CRM", "SALESFORCE": "CRM",
    "ADBE": "ADBE", "ADOBE": "ADBE",
}


# --- Regex fallbacks (run only if the lookup tables miss) -------------------

# 'EUR/USD', 'EURUSD', 'EUR USD' style 6-letter forex pair (no slash needed
# because forex tickers are always 6 ISO-4217 letters glued together).
_FOREX_PAIR_RE = re.compile(
    r"\b([A-Z]{3})\s*[/\s]?\s*([A-Z]{3})\b"
)
# Gold's XAU/USD notation is the only FX-like pair accepted here.
_ISO_FX_CODES = {
    "XAU", "USD",
}

# 'BTC/USDT' or 'ETH-USDT' style explicit crypto pairs — the long-tail
# coverage for the lookup table.
_CRYPTO_PAIR_RE = re.compile(
    r"\b([A-Z0-9]{2,10})\s*[/\-]?\s*(USDT|USDC|BUSD|USD|BTC|ETH)\b"
)

# Bare 1-5 letter all-caps token that *might* be a US stock ticker.
# We require word boundaries and uppercase to avoid matching random words.
_STOCK_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")

# A small stop-list of tokens that look like stock tickers but are normal
# English words / strategy keywords. Without this 'A', 'I', 'IT', 'IS',
# 'TREND', 'GRID' etc. would constantly false-positive as tickers.
_STOCK_FALSE_POSITIVES = {
    # Plain English stop-words that show up as 1-3 letter all-caps after
    # `_normalize` upper-cases the entire prompt.
    "A", "I", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE",
    "IF", "IN", "IS", "IT", "ME", "MY", "NO", "OF", "ON", "OR", "SO",
    "TO", "UP", "US", "WE", "AND", "ARE", "BUT", "CAN", "FOR", "GET",
    "HAS", "NOT", "NOW", "OUR", "OUT", "SET", "THE", "WAS", "WHO",
    "WHY", "YOU", "FROM", "INTO", "JUST", "ONLY", "THAT", "THIS",
    "WHAT", "WHEN", "WITH", "AI", "API", "USA", "UK", "EU", "CEO",
    "CFO", "CTO", "ETF", "IPO", "P2P",
    # Common bot / strategy / indicator vocabulary that appears in user
    # prompts and must NOT be interpreted as a stock ticker.
    "BOT", "BOTS", "DCA", "MA", "EMA", "SMA", "WMA", "RSI", "ATR",
    "MACD", "BUY", "SELL", "LONG", "SHORT", "GRID", "TREND", "TRADE",
    "TRADER", "TRADING", "STOP", "LOSS", "TAKE", "PROFIT", "TP", "SL",
    "PNL", "ROI", "OK", "SCALPING", "SCALP", "SWING", "DAY", "INTRA",
    "MARTIN", "MARTINGALE", "STRATEGY", "BOTPLEASE",
    # Crypto names are handled by _CRYPTO_MAP, not by the stock fallback.
    "BTC", "ETH",
}


# Word-boundary helper: Python's `\b` treats Chinese characters as word
# characters under default Unicode mode, so `\bXAU\b` does NOT match in
# negative lookarounds against [A-Z0-9] instead, which works regardless of
# whether the surrounding characters are CJK, punctuation or whitespace.
def _wbound(token: str) -> str:
    return rf"(?<![A-Z0-9]){re.escape(token)}(?![A-Z0-9])"


def _normalize(prompt: str) -> str:
    """Upper-case + collapse whitespace so lookups are stable."""
    return re.sub(r"\s+", " ", (prompt or "").upper()).strip()


def _lookup_table_match(tokens_upper: str) -> Optional[Tuple[str, str]]:
    """Try the explicit lookup tables in precedence order.

    Forex first: gold is the only FX-like instrument. Vietnamese stocks then
    take precedence over the US fallback for the curated VN symbols.
    """
    for token, sym in _FOREX_MAP.items():
        if re.search(_wbound(token), tokens_upper):
            return ("Forex", sym)
    for token, sym in _VNSTOCK_MAP.items():
        if re.search(_wbound(token), tokens_upper):
            return ("VNStock", sym)
    for token, sym in _CRYPTO_MAP.items():
        if re.search(_wbound(token), tokens_upper):
            return ("Crypto", sym)
    for token, sym in _USSTOCK_MAP.items():
        if re.search(_wbound(token), tokens_upper):
            return ("USStock", sym)
    return None


def _regex_forex_pair(tokens_upper: str) -> Optional[Tuple[str, str]]:
    """Detect the explicit XAU/USD gold notation."""
    for m in _FOREX_PAIR_RE.finditer(tokens_upper):
        a, b = m.group(1), m.group(2)
        if a == "XAU" and b == "USD":
            return ("Forex", "XAUUSD")
    return None


def _regex_crypto_pair(tokens_upper: str) -> Optional[Tuple[str, str]]:
    """Detect BTC/USDT / SOL-USDT style pairs not in the table."""
    m = _CRYPTO_PAIR_RE.search(tokens_upper)
    if not m:
        return None
    base, quote = m.group(1), m.group(2)
    # Skip pairs that look like forex (e.g. 'EUR/USD' would have matched
    # _regex_forex_pair already; the order in detect_market_and_symbol
    # makes sure forex is tried first).
    return ("Crypto", f"{base}/{quote}")


def _regex_stock_ticker(tokens_upper: str) -> Optional[Tuple[str, str]]:
    """Last-ditch fallback: an unknown 1-5 letter token might be a stock."""
    for m in _STOCK_TICKER_RE.finditer(tokens_upper):
        ticker = m.group(1)
        if ticker in _STOCK_FALSE_POSITIVES:
            continue
        # If we get here the ticker wasn't in any of our explicit lookups
        # *and* isn't a stop-word. Treat it as a US stock ticker; the
        # downstream kline call will tell us if it's invalid.
        return ("USStock", ticker)
    return None


def detect_market_and_symbol(prompt: str) -> Optional[Tuple[str, str]]:
    """Return (market_category, canonical_symbol) detected from prompt.

    Returns None if no plausible symbol can be extracted, in which case the
    caller should skip the market-data injection and let the LLM answer
    purely from the user's description.

    Detection order is deliberate:
      1. Explicit lookup tables (Forex first to disambiguate 'XAU/USD').
      2. Gold pair regex (handles 'XAU/USD').
      3. Crypto pair regex (handles 'PEPE/USDT' not in the table).
      4. US stock ticker regex (last resort: any leftover all-caps word).
    """
    norm = _normalize(prompt)
    if not norm:
        return None
    return (
        _lookup_table_match(norm)
        or _regex_forex_pair(norm)
        or _regex_crypto_pair(norm)
        or _regex_stock_ticker(norm)
    )
