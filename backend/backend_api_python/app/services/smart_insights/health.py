"""Freshness classification for Smart Insights source health."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def classify_freshness(
    observed_at: datetime | None,
    *,
    now: datetime | None = None,
    sla_minutes: int,
) -> str:
    if observed_at is None:
        return "UNAVAILABLE"
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if sla_minutes <= 0:
        raise ValueError("sla_minutes must be positive")
    return "FRESH" if current - observed_at <= timedelta(minutes=sla_minutes) else "STALE"


__all__ = ["classify_freshness"]
