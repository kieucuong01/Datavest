"""Native-currency portfolio valuation; never infer FX or missing prices."""
from __future__ import annotations
import math


def quote_currency(position: dict) -> str:
    if position.get("market") == "VNStock":
        return "VND"
    if position.get("market") == "Forex":
        return "USD"
    symbol = str(position.get("symbol") or "").upper()
    return symbol.split("/", 1)[1].split(":", 1)[0] if "/" in symbol else "USDT"


def enrich_positions_with_prices(positions: list[dict], price_map: dict) -> list[dict]:
    for position in positions:
        price_data = price_map.get(f"{position['market']}:{position['symbol']}", {})
        try:
            price = float(price_data.get("price"))
        except (TypeError, ValueError, OverflowError):
            price = None
        status = str(price_data.get("status") or "").upper()
        valid = price is not None and math.isfinite(price) and price > 0 and status not in {"UNAVAILABLE", "ERROR", "FAILED"}
        position["quote_currency"] = quote_currency(position)
        unit = "share" if position["market"] == "VNStock" else "troy_oz" if position["market"] == "Forex" else "token"
        position["price_unit"] = f"{position['quote_currency']}/{unit}"
        position["price_source"] = price_data.get("source")
        position["price_observed_at"] = price_data.get("observedAt") or price_data.get("tradeDate")
        position["price_retrieved_at"] = price_data.get("retrievedAt")
        position["valuation_status"] = "UNAVAILABLE" if not valid else "STALE" if price_data.get("stale") or status == "STALE" else "AVAILABLE"
        position["current_price"] = price if valid else None
        position["price_change"] = price_data.get("change") if valid else None
        position["price_change_percent"] = price_data.get("changePercent") if valid else None
        entry_price, quantity = float(position["entry_price"]), float(position["quantity"])
        cost = entry_price * quantity
        position["cost_value"] = cost
        position["market_value"] = price * quantity if valid else None
        pnl = (price - entry_price) * quantity * (-1 if position.get("side") == "short" else 1) if valid else None
        position["pnl"] = pnl
        position["pnl_percent"] = round(pnl / cost * 100, 2) if pnl is not None and cost > 0 else None
    return positions


def _summarize_currency(rows: list[dict], currency: str) -> dict:
    valued = [row for row in rows if row["market_value"] is not None]
    complete = len(valued) == len(rows)
    cost = sum(row["cost_value"] for row in rows)
    value = sum(row["market_value"] for row in valued)
    pnl = sum(row["pnl"] for row in valued)
    markets = {}
    for row in valued:
        markets[row["market"]] = markets.get(row["market"], 0) + row["market_value"]
    status = "UNAVAILABLE" if rows and not valued else "PARTIAL" if not complete else "STALE" if any(row["valuation_status"] == "STALE" for row in rows) else "AVAILABLE"
    return {
        "currency": currency, "valuation_status": status,
        "total_cost": round(cost, 2),
        "total_market_value": round(value, 2) if complete else None,
        "total_pnl": round(pnl, 2) if complete else None,
        "total_pnl_percent": round(pnl / cost * 100, 2) if complete and cost > 0 else 0 if not rows else None,
        "valued_market_value": round(value, 2),
        "position_count": len(rows), "valued_position_count": len(valued),
        "stale_position_count": sum(row["valuation_status"] == "STALE" for row in rows),
        "market_distribution": sorted([
            {"market": market, "value": round(amount, 2), "percent": round(amount / value * 100, 2) if value else 0}
            for market, amount in markets.items()
        ], key=lambda item: item["value"], reverse=True) if complete else [],
    }


def summarize_position_rows(rows, price_map: dict) -> dict:
    positions = enrich_positions_with_prices([dict(row) for row in rows], price_map)
    currencies = sorted({row["quote_currency"] for row in positions})
    groups = [_summarize_currency([row for row in positions if row["quote_currency"] == currency], currency) for currency in currencies]
    if len(groups) <= 1:
        return {**(groups[0] if groups else _summarize_currency([], "")), "currency_summaries": groups, "mixed_currencies": False}
    return {
        "total_cost": None, "total_market_value": None, "total_pnl": None, "total_pnl_percent": None,
        "currency": None, "mixed_currencies": True, "currency_summaries": groups,
        "position_count": len(positions), "valued_position_count": sum(group["valued_position_count"] for group in groups),
        "valuation_status": "PARTIAL" if any(group["valuation_status"] in {"PARTIAL", "UNAVAILABLE"} for group in groups) else "STALE" if any(group["valuation_status"] == "STALE" for group in groups) else "AVAILABLE",
        "market_distribution": [],
    }


def empty_portfolio_summary() -> dict:
    return summarize_position_rows([], {})
