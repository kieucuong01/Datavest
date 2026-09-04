"""Small, shared provenance contract for Smart Insights responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from app.utils.timeutil import vietnam_timezone


def vietnam_iso(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(vietnam_timezone()).replace(microsecond=0).isoformat()


def freshness_for_status(status: Any, *, historical: bool = False) -> str:
    normalized = str(status or "UNAVAILABLE").upper()
    if normalized in {"COMPLETE", "AVAILABLE"}:
        return "HISTORICAL" if historical else "FRESH"
    if normalized == "PARTIAL":
        return "PARTIAL"
    if normalized == "STALE":
        return "STALE"
    return "UNAVAILABLE"


def attach_data_contract(
    payload: Mapping[str, Any],
    *,
    requested_as_of: str | None,
    resolved_as_of: str | None,
    fetched_at: datetime | None = None,
    freshness: str | None = None,
    coverage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Add explicit date, freshness, and coverage fields without changing payload data."""
    result = dict(payload)
    status = str(result.get("status") or "UNAVAILABLE").upper()
    result.update({
        "requestedAsOf": requested_as_of,
        "resolvedAsOf": resolved_as_of,
        "fetchedAt": vietnam_iso(fetched_at),
        "freshness": freshness or freshness_for_status(status),
        "coverage": dict(coverage or {}),
    })
    return result


__all__ = ["attach_data_contract", "freshness_for_status", "vietnam_iso"]
