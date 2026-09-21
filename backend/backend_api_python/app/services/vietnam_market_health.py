"""Durable, non-secret operational health for the free Vietnam market feeds."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import json
from typing import Any


def classify_provider_health(outcomes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Normalize probe outcomes without retaining provider exception details."""

    providers: list[dict[str, Any]] = []
    for item in outcomes:
        status = str(item.get("status") or "unavailable").strip().lower()
        status = status if status in {"ok", "stale", "empty", "unavailable"} else "unavailable"
        row = {
            "provider": str(item.get("provider") or "unknown")[:80],
            "status": status,
            "bars": max(0, int(item.get("bars") or 0)),
        }
        error = str(item.get("error") or "").strip().lower()
        if error:
            row["error"] = error[:80]
        providers.append(row)

    available = sum(1 for item in providers if item["status"] == "ok")
    if not providers or available == 0:
        status = "unavailable"
    elif available == len(providers):
        status = "healthy"
    else:
        status = "degraded"
    return {"status": status, "availableProviders": available, "providers": providers}


def finalize_eod_batch(
    *,
    total_symbols: int,
    successful_symbols: int,
    minimum_coverage: float,
    source_health: Mapping[str, Any],
) -> dict[str, Any]:
    """Gate a full-universe write: a partial batch must not change durable rows."""

    total = max(0, int(total_symbols))
    successful = min(total, max(0, int(successful_symbols)))
    threshold = min(1.0, max(0.01, float(minimum_coverage)))
    coverage = successful / total if total else 0.0
    flags: list[str] = []
    persist = total > 0 and coverage >= threshold
    if not persist:
        flags.append("batch_coverage_below_minimum")
    source_status = str(source_health.get("status") or "unavailable")
    status = "complete" if persist and source_status == "healthy" else "degraded" if persist else "incomplete"
    return {
        "status": status,
        "totalSymbols": total,
        "successfulSymbols": successful,
        "coverage": coverage,
        "minimumCoverage": threshold,
        "persist": persist,
        "flags": flags,
        "sourceHealth": dict(source_health),
    }


class VietnamMarketHealthRepository:
    """Persist summary snapshots only; price rows remain in their existing table."""

    def record(self, *, result: Mapping[str, Any], trigger: str) -> None:
        from app.utils.db import get_db_connection

        payload = json.dumps(dict(result), ensure_ascii=False, sort_keys=True)
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO qd_vietnam_market_health (trigger_type, status, coverage, result, checked_at)
                    VALUES (?, ?, ?, ?::jsonb, ?)
                    """,
                    (
                        str(trigger or "scheduled")[:40],
                        str(result.get("status") or "incomplete")[:24],
                        float(result.get("coverage") or 0.0),
                        payload,
                        datetime.now(timezone.utc),
                    ),
                )
                db.commit()
            finally:
                cur.close()


__all__ = ["VietnamMarketHealthRepository", "classify_provider_health", "finalize_eod_batch"]
