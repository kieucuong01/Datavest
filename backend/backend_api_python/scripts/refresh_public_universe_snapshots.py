"""Refresh versioned current-universe snapshots from public sources."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.symbol_master_sync import SymbolMasterRow, upsert_symbol_master
from app.utils.db import get_db_connection


SP500_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
NASDAQ100_URL = "https://raw.githubusercontent.com/Gary-Strauss/NASDAQ100_Constituents/master/data/nasdaq100_constituents.csv"
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"

CURATED_ETF_SYMBOLS = {
    "USStock": (
        "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "IVV", "EFA", "EEM", "AGG", "BND", "TLT",
        "IEF", "GLD", "SLV", "USO", "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU",
        "VNQ", "ARKK", "HYG", "LQD", "SCHD", "VUG", "VTV",
    ),
}

EXPECTED_MEMBER_COUNTS = {
    "sp500": (500, 510),
    "nasdaq100": (100, 102),
    "crypto_top100": (95, 100),
    "us_etf": (1, 1000),
}

def _csv_rows(url: str) -> list[dict]:
    response = requests.get(url, timeout=30, headers={"User-Agent": "QuantDinger/4.0"})
    response.raise_for_status()
    return list(csv.DictReader(io.StringIO(response.text)))


def sp500() -> list[dict]:
    return [
        {
            "market": "USStock",
            "symbol": str(row.get("Symbol") or "").strip().upper(),
            "name": str(row.get("Security") or "").strip(),
            "rank": index,
            "metadata": {
                "sector": row.get("GICS Sector") or "",
                "sub_industry": row.get("GICS Sub-Industry") or "",
                "headquarters": row.get("Headquarters Location") or "",
                "date_added": row.get("Date added") or "",
                "cik": row.get("CIK") or "",
            },
        }
        for index, row in enumerate(_csv_rows(SP500_URL), start=1)
        if row.get("Symbol")
    ]


def nasdaq100() -> list[dict]:
    return [
        {
            "market": "USStock",
            "symbol": str(row.get("Ticker") or "").strip().upper(),
            "name": str(row.get("Company") or "").strip(),
            "rank": index,
            "metadata": {
                "sector": row.get("GICS_Sector") or "",
                "sub_industry": row.get("GICS_Sub_Industry") or "",
            },
        }
        for index, row in enumerate(_csv_rows(NASDAQ100_URL), start=1)
        if row.get("Ticker")
    ]


def crypto_top100() -> list[dict]:
    response = requests.get(
        COINGECKO_URL,
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false",
        },
        timeout=30,
        headers={"User-Agent": "QuantDinger/4.0"},
    )
    response.raise_for_status()
    rows = []
    seen = set()
    for item in response.json():
        symbol = f"{str(item.get('symbol') or '').upper()}/USDT"
        if symbol in seen or symbol == "/USDT":
            continue
        seen.add(symbol)
        rows.append({
            "market": "Crypto",
            "symbol": symbol,
            "name": str(item.get("name") or ""),
            "rank": int(item.get("market_cap_rank") or len(rows) + 1),
            "metadata": {
                "coingecko_id": item.get("id") or "",
                "market_cap_usd": item.get("market_cap"),
                "circulating_supply": item.get("circulating_supply"),
                "total_volume_usd": item.get("total_volume"),
            },
        })
    return rows


def symbol_master_etfs(market: str) -> list[dict]:
    """Build an ETF snapshot and repair legacy curated ETF metadata."""
    with get_db_connection() as db:
        cur = db.cursor()
        curated = list(CURATED_ETF_SYMBOLS.get(market, ()))
        if curated:
            cur.execute(
                """
                UPDATE qd_market_symbols
                SET asset_class = 'etf', is_hot = 1, sort_order = GREATEST(sort_order, 80)
                WHERE market = ? AND symbol = ANY(?)
                """,
                (market, curated),
            )
        cur.execute(
            """
            SELECT market, symbol, name
            FROM qd_market_symbols
            WHERE market = ? AND is_active = 1 AND is_hot = 1 AND asset_class = 'etf'
            ORDER BY sort_order DESC, symbol
            """,
            (market,),
        )
        rows = cur.fetchall() or []
        db.commit()
        cur.close()
    return [
        {
            "market": str(row.get("market") or market),
            "symbol": str(row.get("symbol") or "").strip().upper(),
            "name": str(row.get("name") or "").strip(),
            "rank": index,
            "metadata": {"source": "symbol_master", "asset_class": "etf"},
        }
        for index, row in enumerate(rows, start=1)
        if row.get("symbol")
    ]


LOADERS = {
    "sp500": sp500,
    "nasdaq100": nasdaq100,
    "crypto_top100": crypto_top100,
    "us_etf": lambda: symbol_master_etfs("USStock"),
}

SOURCE_METADATA = {
    "sp500": {"url": SP500_URL, "license": "ODC-PDDL", "snapshot_only": True},
    "nasdaq100": {"url": NASDAQ100_URL, "license": "MIT scraper; source data CC BY-SA", "snapshot_only": True},
    "crypto_top100": {"url": COINGECKO_URL, "snapshot_only": True},
    "us_etf": {"adapter": "symbol_master", "market": "USStock", "asset_class": "etf", "snapshot_only": True},
}


def apply_snapshot(code: str, members: list[dict], as_of: date, *, dry_run: bool = False) -> dict:
    clean = {item["symbol"]: item for item in members if item.get("symbol")}
    if dry_run:
        return {"code": code, "members": len(clean), "dry_run": True}
    with get_db_connection() as db:
        cur = db.cursor()
        cur.execute("SELECT id FROM qd_universes WHERE code = ? AND is_system = TRUE", (code,))
        universe = cur.fetchone() or {}
        universe_id = int(universe.get("id") or 0)
        if not universe_id:
            raise RuntimeError(f"unknown system universe: {code}")
        cur.execute(
            "SELECT symbol, valid_from FROM qd_universe_members WHERE universe_id = ? AND valid_to IS NULL",
            (universe_id,),
        )
        active_rows = cur.fetchall() or []
        active = {str(row.get("symbol") or "") for row in active_rows}
        active_from = {str(row.get("symbol") or ""): row.get("valid_from") for row in active_rows}
        removed = active - set(clean)
        if removed:
            same_day = [symbol for symbol in removed if active_from.get(symbol) and active_from[symbol] >= as_of]
            historical = sorted(removed - set(same_day))
            if same_day:
                cur.execute(
                    "DELETE FROM qd_universe_members WHERE universe_id = ? AND valid_to IS NULL AND symbol = ANY(?)",
                    (universe_id, sorted(same_day)),
                )
            if historical:
                cur.execute(
                    "UPDATE qd_universe_members SET valid_to = ? WHERE universe_id = ? AND valid_to IS NULL AND symbol = ANY(?)",
                    (as_of, universe_id, historical),
                )
        for symbol, item in clean.items():
            metadata = json.dumps(item.get("metadata") or {}, ensure_ascii=False)
            if symbol in active:
                cur.execute(
                    """
                    UPDATE qd_universe_members
                    SET name = ?, member_weight = ?, member_rank = ?, metadata_json = ?, source_version = ?
                    WHERE universe_id = ? AND symbol = ? AND valid_to IS NULL
                    """,
                    (item.get("name") or "", item.get("weight"), item.get("rank"), metadata, as_of.isoformat(), universe_id, symbol),
                )
                continue
            cur.execute(
                """
                INSERT INTO qd_universe_members
                  (universe_id, market, symbol, name, market_type, valid_from,
                   member_weight, member_rank, source_version, metadata_json)
                VALUES (?, ?, ?, ?, 'spot', ?, ?, ?, ?, ?)
                """,
                (
                    universe_id, item.get("market") or "", symbol, item.get("name") or "",
                    as_of, item.get("weight"), item.get("rank"), as_of.isoformat(), metadata,
                ),
            )
        universe_metadata = json.dumps(
            {**SOURCE_METADATA.get(code, {}), "snapshot_as_of": as_of.isoformat()},
            ensure_ascii=False,
        )
        cur.execute(
            """
            UPDATE qd_universes
            SET status = 'active', source = 'public_snapshot', metadata_json = ?, updated_at = NOW()
            WHERE id = ?
            """,
            (universe_metadata, universe_id),
        )
        db.commit()
        cur.close()
    return {"code": code, "members": len(clean), "added": len(set(clean) - active), "removed": len(removed)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universes", default=",".join(LOADERS))
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of)
    results = []
    for code in [item.strip() for item in args.universes.split(",") if item.strip()]:
        loader = LOADERS.get(code)
        if loader is None:
            raise RuntimeError(f"unsupported universe: {code}")
        members = loader()
        minimum, maximum = EXPECTED_MEMBER_COUNTS[code]
        if not minimum <= len({item.get("symbol") for item in members}) <= maximum:
            raise RuntimeError(f"{code} member count failed validation: {len(members)}")
        results.append(apply_snapshot(code, members, as_of, dry_run=args.dry_run))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
