"""Compute helpers for global market dashboard routes."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from app.data_providers import set_cached
from app.data_providers.crypto import fetch_crypto_prices
from app.data_providers.forex import fetch_forex_pairs
from app.data_providers.opportunities import (
    analyze_opportunities_crypto,
    analyze_opportunities_forex,
    analyze_opportunities_local_stocks,
    analyze_opportunities_stocks,
    fetch_local_stock_opportunity_prices,
)
from app.data_providers.sentiment import (
    fetch_dollar_index,
    fetch_fear_greed_index,
    fetch_gvz,
    fetch_put_call_ratio,
    fetch_vix,
    fetch_vxn,
    fetch_yield_curve,
)
from app.utils.logger import get_logger
from app.utils.market_visibility import is_market_visible

logger = get_logger(__name__)


def compute_market_overview() -> Dict[str, Any]:
    """Fetch the supported US/Vietnam/crypto/gold market overview."""
    result: Dict[str, Any] = {
        "us_stocks": [],
        "vn_stocks": [],
        "crypto": [],
        "gold": [],
        "timestamp": int(time.time()),
    }
    jobs = {}
    if is_market_visible("VNStock"):
        jobs["vn_stocks"] = lambda: fetch_local_stock_opportunity_prices("VNStock", 15, fast=True)
    if is_market_visible("Crypto"):
        jobs["crypto"] = fetch_crypto_prices
    if is_market_visible("Forex"):
        jobs["gold"] = fetch_forex_pairs
    with ThreadPoolExecutor(max_workers=max(len(jobs), 1)) as executor:
        futures = {executor.submit(job): key for key, job in jobs.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                data = future.result()
                result[key] = data if data else []
            except Exception as exc:
                logger.error("Failed to fetch %s: %s", key, exc, exc_info=True)
                result[key] = []

    logger.info(
        "Market overview compute: us_stocks=%d, vn_stocks=%d, crypto=%d, gold=%d",
        len(result["us_stocks"]),
        len(result["vn_stocks"]),
        len(result["crypto"]),
        len(result["gold"]),
    )
    # US remains an internal future-reenable market, but the current product
    # does not fetch or expose it by default.
    set_cached("us_stock_opportunity_prices", result["us_stocks"])
    set_cached("stock_opportunity_prices", result["us_stocks"])
    set_cached("vn_stock_opportunity_prices", result["vn_stocks"])
    set_cached("forex_pairs", result["gold"])
    set_cached("crypto_prices", result["crypto"])
    return result


def compute_market_sentiment() -> Dict[str, Any]:
    """Fetch macro sentiment indicators in parallel with neutral fallbacks."""
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            executor.submit(fetch_fear_greed_index): "fear_greed",
            executor.submit(fetch_vix): "vix",
            executor.submit(fetch_dollar_index): "dxy",
            executor.submit(fetch_yield_curve): "yield_curve",
            executor.submit(fetch_vxn): "vxn",
            executor.submit(fetch_gvz): "gvz",
            executor.submit(fetch_put_call_ratio): "vix_term",
        }
        results: Dict[str, Any] = {}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                logger.error("Failed to fetch %s: %s", key, exc)
                results[key] = None

    logger.info(
        "Sentiment compute: Fear&Greed=%s, VIX=%s, DXY=%s",
        (results.get("fear_greed") or {}).get("value"),
        (results.get("vix") or {}).get("value"),
        (results.get("dxy") or {}).get("value"),
    )
    return {
        "fear_greed": results.get("fear_greed") or {"value": 50, "classification": "Neutral"},
        "vix": results.get("vix") or {"value": 0, "level": "unknown"},
        "dxy": results.get("dxy") or {"value": 0, "level": "unknown"},
        "yield_curve": results.get("yield_curve") or {"spread": 0, "level": "unknown"},
        "vxn": results.get("vxn") or {"value": 0, "level": "unknown"},
        "gvz": results.get("gvz") or {"value": 0, "level": "unknown"},
        "vix_term": results.get("vix_term") or {"value": 1.0, "level": "unknown"},
        "timestamp": int(time.time()),
    }


def compute_trading_opportunities() -> List[Dict[str, Any]]:
    """Run enabled market scanners and return sorted opportunity rows."""
    opportunities: List[Dict[str, Any]] = []
    candidate_scanners = [
        ("Crypto", lambda: analyze_opportunities_crypto(opportunities)),
        ("USStock", lambda: analyze_opportunities_stocks(opportunities)),
        ("Forex", lambda: analyze_opportunities_forex(opportunities)),
        ("VNStock", lambda: analyze_opportunities_local_stocks(opportunities, "VNStock")),
    ]
    scanners = [(label, fn) for label, fn in candidate_scanners if is_market_visible(label)]
    for label, scanner in scanners:
        try:
            scanner()
            count = len([item for item in opportunities if item.get("market") == label])
            logger.info("Trading opportunities: found %d %s opportunities", count, label)
        except Exception as exc:
            logger.error("Failed to analyze %s opportunities: %s", label, exc, exc_info=True)

    opportunities.sort(key=lambda item: abs(item.get("change_24h", 0)), reverse=True)
    by_market: Dict[str, int] = {}
    for item in opportunities:
        market = item.get("market", "?")
        by_market[market] = by_market.get(market, 0) + 1
    logger.info("Trading opportunities: total %d (%s)", len(opportunities), by_market)
    return opportunities
