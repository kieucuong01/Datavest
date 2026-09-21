"""Scheduled, all-or-nothing EOD ingestion for the active HOSE universe."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.celery_app import celery_app
from app.data_sources.vn_stock import VNStockDataSource
from app.data.market_symbols_seed import validate_hose_ai_target
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


def backfill_hose_history(
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    source: Any | None = None,
) -> dict[str, Any]:
    """Bounded operator backfill; incomplete provider history stays an explicit gap."""

    canonical = validate_hose_ai_target("VNStock", symbol)
    start = date.fromisoformat(str(start_date))
    end = date.fromisoformat(str(end_date))
    if end < start or (end - start).days + 1 > 3660:
        raise ValueError("invalid_hose_backfill_window")
    source = source or VNStockDataSource()
    zone = ZoneInfo("Asia/Ho_Chi_Minh")
    after_time = int(datetime.combine(start, datetime.min.time(), tzinfo=zone).timestamp())
    before_time = int(datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=zone).timestamp())
    bars = source.get_kline(
        canonical, "1D", (end - start).days + 1,
        after_time=after_time, before_time=before_time, price_mode="raw",
    )
    expected_sessions = sum(
        1 for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() < 5
    )
    quality = dict(getattr(source, "last_kline_quality", {}) or {})
    coverage = min(1.0, len(bars) / max(expected_sessions, 1))
    provider_coverage = float(quality.get("coverage", coverage) or 0.0)
    coverage = min(coverage, provider_coverage) if bars else 0.0
    gaps = [] if coverage >= 0.95 else [{"field": "dailyPrices", "reason": "HISTORICAL_COVERAGE_INCOMPLETE"}]
    return {
        "market": "VNStock", "symbol": canonical,
        "startDate": start.isoformat(), "endDate": end.isoformat(),
        "bars": len(bars), "coverage": coverage,
        "provider": str(getattr(source, "last_kline_provider", "") or "") or None,
        "attempts": list(getattr(source, "last_kline_attempts", ()) or ()),
        "qualityFlags": list(quality.get("flags", []) or []),
        "dataGaps": gaps,
    }


@celery_app.task(name="datavest.tasks.hose_eod_ingestion", acks_late=True)
def run_hose_eod_ingestion() -> dict[str, Any]:
    return ingest_hose_eod(trigger="scheduled")


@celery_app.task(name="datavest.tasks.hose_history_backfill", acks_late=True)
def run_hose_history_backfill(symbol: str, start_date: str, end_date: str) -> dict[str, Any]:
    return backfill_hose_history(symbol=symbol, start_date=start_date, end_date=end_date)


__all__ = ["backfill_hose_history", "ingest_hose_eod", "run_hose_eod_ingestion", "run_hose_history_backfill"]
