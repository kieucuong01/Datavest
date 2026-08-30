#!/usr/bin/env python3
"""Generate an idempotent SQL seed file for qd_market_symbols."""

from __future__ import annotations

import argparse
import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple


Row = Tuple[str, str, str, str, str]


STATIC_MARKET_ROWS: List[Row] = [
    ("USStock", "MSFT", "Microsoft Corporation", "NASDAQ", "USD"),
    ("USStock", "GOOGL", "Alphabet Inc.", "NASDAQ", "USD"),
    ("USStock", "AAPL", "Apple Inc.", "NASDAQ", "USD"),
    ("USStock", "TSLA", "Tesla Inc.", "NASDAQ", "USD"),
    ("USStock", "NVDA", "NVIDIA Corporation", "NASDAQ", "USD"),
    ("Crypto", "BTC/USDT", "Bitcoin", "binance", "USDT"),
    ("Crypto", "ETH/USDT", "Ethereum", "binance", "USDT"),
    ("Crypto", "BNB/USDT", "BNB", "binance", "USDT"),
    ("Crypto", "SOL/USDT", "Solana", "binance", "USDT"),
    ("Crypto", "XRP/USDT", "XRP", "binance", "USDT"),
    ("Crypto", "DOGE/USDT", "Dogecoin", "binance", "USDT"),
    ("Crypto", "ADA/USDT", "Cardano", "binance", "USDT"),
    ("Crypto", "AVAX/USDT", "Avalanche", "binance", "USDT"),
    ("Crypto", "LINK/USDT", "Chainlink", "binance", "USDT"),
    ("Crypto", "DOT/USDT", "Polkadot", "binance", "USDT"),
    ("Crypto", "TRX/USDT", "TRON", "binance", "USDT"),
    ("Crypto", "TON/USDT", "Toncoin", "binance", "USDT"),
    ("Crypto", "LTC/USDT", "Litecoin", "binance", "USDT"),
    ("Crypto", "BCH/USDT", "Bitcoin Cash", "binance", "USDT"),
    ("Crypto", "UNI/USDT", "Uniswap", "binance", "USDT"),
    ("Crypto", "AAVE/USDT", "Aave", "binance", "USDT"),
    ("Crypto", "MATIC/USDT", "Polygon", "binance", "USDT"),
    ("Crypto", "NEAR/USDT", "NEAR Protocol", "binance", "USDT"),
    ("Crypto", "APT/USDT", "Aptos", "binance", "USDT"),
    ("Crypto", "ARB/USDT", "Arbitrum", "binance", "USDT"),
    ("Crypto", "OP/USDT", "Optimism", "binance", "USDT"),
    ("Crypto", "FIL/USDT", "Filecoin", "binance", "USDT"),
    ("Crypto", "ETC/USDT", "Ethereum Classic", "binance", "USDT"),
    ("Crypto", "ATOM/USDT", "Cosmos", "binance", "USDT"),
    ("Crypto", "INJ/USDT", "Injective", "binance", "USDT"),
    ("Crypto", "SUI/USDT", "Sui", "binance", "USDT"),
    ("Crypto", "SEI/USDT", "Sei", "binance", "USDT"),
    ("Crypto", "PEPE/USDT", "Pepe", "binance", "USDT"),
    ("Crypto", "SHIB/USDT", "Shiba Inu", "binance", "USDT"),
    ("Crypto", "WLD/USDT", "Worldcoin", "binance", "USDT"),
    ("Forex", "XAUUSD", "Gold Spot", "TwelveData", "USD"),
    ("VNStock", "FPT", "FPT Corporation", "HOSE", "VND"),
    ("VNStock", "VCB", "Vietcombank", "HOSE", "VND"),
    ("VNStock", "HPG", "Hoa Phat Group", "HOSE", "VND"),
    ("VNStock", "VIC", "Vingroup", "HOSE", "VND"),
    ("VNStock", "VHM", "Vinhomes", "HOSE", "VND"),
    ("VNStock", "VNM", "Vinamilk", "HOSE", "VND"),
    ("VNStock", "SSI", "SSI Securities", "HOSE", "VND"),
    ("VNStock", "MWG", "Mobile World", "HOSE", "VND"),
]

CURATED_ETF_SYMBOLS = {
    "USStock": (
        "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "IVV", "EFA", "EEM", "AGG", "BND", "TLT",
        "IEF", "GLD", "SLV", "USO", "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU",
        "VNQ", "ARKK", "HYG", "LQD", "SCHD", "VUG", "VTV",
    ),
}


def clean(value: object) -> str:
    return str(value or "").strip()


def repair_mojibake(value: object) -> str:
    text = clean(value)
    if not text:
        return ""
    suspicious = any(ch in text for ch in ("\u9a9e", "\u95be", "\u934f", "\u6d93", "\u6df1", "\u7eee", "\u60f0"))
    if not suspicious:
        return text
    for enc in ("gbk", "cp936", "latin1"):
        try:
            fixed = text.encode(enc).decode("utf-8")
            if fixed and fixed != text:
                return fixed
        except Exception:
            pass
    return text


def normalize_crypto_symbol(symbol: str) -> str:
    sym = clean(symbol).upper()
    if ":" in sym:
        sym = sym.split(":", 1)[0]
    if "/" in sym:
        base, quote = sym.split("/", 1)
        return f"{base}/{quote}" if base and quote else sym
    for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
        if sym.endswith(quote) and len(sym) > len(quote):
            return f"{sym[:-len(quote)]}/{quote}"
    return f"{sym}/USDT" if sym else ""


class Collector:
    def __init__(self) -> None:
        self.rows: List[Row] = []
        self.seen = set()

    def add(self, market: str, symbol: object, name: object, exchange: str = "", currency: str = "") -> None:
        if market not in {"USStock", "VNStock", "Crypto", "Forex"}:
            return
        if market == "Forex" and clean(symbol).upper().replace("/", "") not in {"XAUUSD"}:
            return
        sym = clean(symbol).upper()
        nm = repair_mojibake(name)
        if not market or not sym or not nm:
            return
        key = (market, sym)
        if key in self.seen:
            return
        self.seen.add(key)
        self.rows.append((market, sym, nm, clean(exchange), clean(currency)))


def add_static_rows(col: Collector, market: str | None = None) -> None:
    for row in STATIC_MARKET_ROWS:
        if market is None or row[0] == market:
            col.add(*row)


def read_nasdaq_file(url: str) -> Iterable[dict]:
    import requests

    resp = requests.get(url, timeout=25)
    resp.raise_for_status()
    lines = [line for line in resp.text.splitlines() if line and not line.startswith("File Creation Time")]
    return csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|")


def add_us_rows(col: Collector) -> None:
    for rec in read_nasdaq_file("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"):
        if clean(rec.get("Test Issue")).upper() == "Y":
            continue
        col.add("USStock", rec.get("Symbol"), rec.get("Security Name"), "NASDAQ", "USD")

    exchange_map = {"A": "NYSE American", "N": "NYSE", "P": "NYSE Arca", "Z": "Cboe BZX", "V": "IEX"}
    for rec in read_nasdaq_file("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"):
        if clean(rec.get("Test Issue")).upper() == "Y":
            continue
        code = clean(rec.get("Exchange")).upper()
        col.add("USStock", rec.get("ACT Symbol"), rec.get("Security Name"), exchange_map.get(code, code), "USD")


def add_crypto_rows(col: Collector) -> None:
    add_static_rows(col, "Crypto")
    import ccxt  # type: ignore

    exchange = ccxt.binance()
    exchange.load_markets()
    for symbol, info in exchange.markets.items():
        if not info.get("active"):
            continue
        base = clean(info.get("base")).upper()
        quote = clean(info.get("quote")).upper()
        if base and quote == "USDT":
            col.add("Crypto", normalize_crypto_symbol(symbol), base, "binance", "USDT")


def add_forex_rows(col: Collector) -> None:
    add_static_rows(col, "Forex")


def sql_quote(value: object) -> str:
    return "'" + clean(value).replace("'", "''") + "'"


def build_sql(rows: List[Row], notes: List[str]) -> str:
    rows = sorted(rows, key=lambda r: (r[0], r[1]))
    out = [
        "-- Auto-generated local symbol master seed.",
        f"-- Generated at {datetime.now(timezone.utc).isoformat()}",
        "-- Refresh with: python scripts/generate_market_symbols_seed_sql.py --output migrations/market_symbols_master.sql",
    ]
    for note in notes:
        out.append(f"-- {note}")
    out.extend(["", "INSERT INTO qd_market_symbols (market, symbol, name, exchange, currency, market_type, instrument_id, is_active, is_hot, sort_order) VALUES"])
    values = [
        "  (" + ", ".join([sql_quote(a), sql_quote(b), sql_quote(c), sql_quote(d), sql_quote(e), "'spot'", "''", "1", "0", "0"]) + ")"
        for a, b, c, d, e in rows
    ]
    out.append(",\n".join(values))
    out.extend([
        "ON CONFLICT (market, symbol, exchange, market_type, instrument_id) DO UPDATE",
        "  SET name = EXCLUDED.name,",
        "      exchange = COALESCE(NULLIF(EXCLUDED.exchange, ''), qd_market_symbols.exchange),",
        "      currency = COALESCE(NULLIF(EXCLUDED.currency, ''), qd_market_symbols.currency),",
        "      is_active = 1;",
        "",
    ])
    for market, symbols in CURATED_ETF_SYMBOLS.items():
        quoted_symbols = ",".join(sql_quote(symbol) for symbol in symbols)
        out.extend([
            "UPDATE qd_market_symbols",
            "SET asset_class = 'etf', is_hot = 1, sort_order = GREATEST(sort_order, 80)",
            f"WHERE market = {sql_quote(market)} AND symbol IN ({quoted_symbols});",
            "",
        ])
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate market symbol seed SQL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--markets",
        nargs="*",
        default=["USStock", "VNStock", "Crypto", "Forex"],
    )
    args = parser.parse_args()

    col = Collector()
    notes: List[str] = []
    for market in ("USStock", "VNStock", "Crypto", "Forex"):
        add_static_rows(col, market)
    fetchers = {
        "USStock": add_us_rows,
        "VNStock": lambda target: add_static_rows(target, "VNStock"),
        "Crypto": add_crypto_rows,
        "Forex": add_forex_rows,
    }
    for market in args.markets:
        fetcher = fetchers.get(market)
        if not fetcher:
            notes.append(f"{market}: unsupported")
            continue
        before = len(col.rows)
        try:
            fetcher(col)
            notes.append(f"{market}: {len(col.rows) - before} rows fetched")
        except Exception as exc:
            notes.append(f"{market}: failed ({exc})")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_sql(col.rows, notes), encoding="utf-8")
    print(f"Wrote {len(col.rows)} rows to {args.output}")
    for note in notes:
        print(note)


if __name__ == "__main__":
    main()
