"""Scheduled, all-or-nothing EOD ingestion for the active HOSE universe."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from typing import Any

from app.celery_app import celery_app
from app.data_sources.vn_stock import VNStockDataSource
from app.services.vietnam_market_health import (
    VietnamMarketHealthRepository,
    classify_provider_health,
    finalize_eod_batch,
)
from app.services.vietnam_market_history import VietnamDailyPriceRepository


def _active_hose_symbols() -> list[str]:
    from app.utils.db import get_db_connection

    with get_db_connection() as db:
        cur = db.cursor()
        try:
            cur.execute(
                """
                SELECT symbol
                  FROM qd_market_symbols
                 WHERE market = 'VNStock' AND exchange = 'HOSE'
                   AND is_active = 1 AND trading_status = 'ACTIVE'
                   AND asset_class IN ('equity', 'etf') AND source = 'vndirect'
                   AND source_updated_at IS NOT NULL
                   AND (delisted_date IS NULL OR delisted_date > CURRENT_DATE)
                 ORDER BY symbol
                """
            )
            return [str(row["symbol"]).upper() for row in cur.fetchall()]
        finally:
            cur.close()


def _minimum_coverage() -> float:
    try:
        return min(1.0, max(0.01, float(os.getenv("HOSE_EOD_MIN_COVERAGE", "0.95"))))
    except ValueError:
        return 0.95


def ingest_hose_eod(
    *,
    symbols: Iterable[str] | None = None,
    source: Any | None = None,
    health_repository: Any | None = None,
    trigger: str = "scheduled",
) -> dict[str, Any]:
    """Fetch one current daily batch and persist only if the whole batch is adequate."""

    pending_writes: list[dict[str, Any]] = []
    if source is None:
        source = VNStockDataSource(history_persist=lambda **payload: pending_writes.append(payload))
    active_symbols = list(symbols) if symbols is not None else _active_hose_symbols()
    active_symbols = [str(symbol).strip().upper() for symbol in active_symbols if str(symbol).strip()]
    provider_outcomes = source.probe_daily_provider_health(active_symbols[0]) if active_symbols else []
    source_health = classify_provider_health(provider_outcomes)
    rows: list[dict[str, Any]] = []
    successful = 0
    for symbol in active_symbols:
        bars = source.get_kline(symbol, "1D", 5, price_mode="raw")
        quality = dict(getattr(source, "last_kline_quality", {}) or {})
        provider = str(getattr(source, "last_kline_provider", "") or "")
        attempts = list(getattr(source, "last_kline_attempts", ()) or ())
        ok = bool(bars) and float(quality.get("coverage", 0.0) or 0.0) > 0
        successful += int(ok)
        rows.append({
            "symbol": symbol,
            "status": "ok" if ok else "missing",
            "provider": provider or None,
            "attempts": attempts,
            "coverage": float(quality.get("coverage", 0.0) or 0.0),
            "flags": list(quality.get("flags", []) or []),
        })
    result = finalize_eod_batch(
        total_symbols=len(active_symbols),
        successful_symbols=successful,
        minimum_coverage=_minimum_coverage(),
        source_health=source_health,
    )
    result["symbols"] = rows
    if result["persist"]:
        for payload in pending_writes:
            VietnamDailyPriceRepository.persist(**payload)
        result["persistedSymbols"] = len(pending_writes)
    else:
        result["persistedSymbols"] = 0
    try:
        (health_repository or VietnamMarketHealthRepository()).record(result=result, trigger=trigger)
    except Exception:
        # The source rows must remain available to the caller even when metrics storage is down.
        result["healthRecord"] = "unavailable"
    return result


@celery_app.task(name="datavest.tasks.hose_eod_ingestion", acks_late=True)
def run_hose_eod_ingestion() -> dict[str, Any]:
    return ingest_hose_eod(trigger="scheduled")


__all__ = ["ingest_hose_eod", "run_hose_eod_ingestion"]
