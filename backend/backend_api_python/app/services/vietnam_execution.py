"""Execution metadata used by Vietnam equity backtests.

The values are configurable assumptions for research simulations.  They are
kept out of the generic broker so non-Vietnam markets retain their existing
execution model.
"""

from __future__ import annotations

import os

import pandas as pd


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return float(default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return int(default)


def enrich_vietnam_execution_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach configurable HOSE execution assumptions to a daily OHLCV frame."""
    enriched = frame.copy()
    if enriched.empty:
        return enriched

    lot_size = max(1.0, _env_float("VN_LOT_SIZE", 100.0))
    settlement_sessions = max(0, _env_int("VN_SETTLEMENT_SESSIONS", 2))
    sell_tax_rate = max(0.0, _env_float("VN_SELL_TAX_RATE", 0.001))
    price_limit_pct = max(0.0, _env_float("VN_PRICE_LIMIT_PCT", 0.07))

    enriched["lot_size"] = lot_size
    enriched["settlement_sessions"] = settlement_sessions
    enriched["sell_tax_rate"] = sell_tax_rate
    enriched["is_suspended"] = enriched["volume"].fillna(0).le(0)

    previous_close = enriched["close"].shift(1)
    locked_price = (
        enriched["open"].eq(enriched["high"])
        & enriched["open"].eq(enriched["low"])
        & enriched["open"].eq(enriched["close"])
    )
    relative_move = enriched["close"].div(previous_close).sub(1.0)
    tolerance = 1e-6
    enriched["limit_up"] = (
        locked_price
        & previous_close.gt(0)
        & relative_move.ge(price_limit_pct - tolerance)
    )
    enriched["limit_down"] = (
        locked_price
        & previous_close.gt(0)
        & relative_move.le(-price_limit_pct + tolerance)
    )
    return enriched
