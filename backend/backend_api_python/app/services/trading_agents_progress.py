"""Safe, observed progress for the native TradingAgents graph.

This module deliberately derives UI progress from graph callbacks that have
already happened. It never estimates time or exposes the upstream report
payloads used to produce the final artifact.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any


_STAGES = (
    "market",
    "social",
    "news",
    "fundamentals",
    "investment_debate",
    "research_manager",
    "trader",
    "risk_debate",
    "portfolio_manager",
    "report",
)
_CRYPTO_STAGES = tuple(stage for stage in _STAGES if stage != "fundamentals")
_ALLOWED_STAGE_IDS = frozenset(_STAGES)
_ALLOWED_TOOL_EVENT_TYPES = frozenset({"tool_started", "tool_completed", "tool"})
_ALLOWED_TOOL_KEYS = frozenset({"tool_name", "category", "vendor_chain", "status", "duration_ms", "result_checksum"})


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _iso(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def public_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the progress-safe portion of one stored event."""

    event_type = str(event.get("event_type") or event.get("kind") or "").strip().lower()
    payload = _json_object(event.get("payload_json") or event.get("payload"))
    safe_payload: dict[str, Any] = {}
    stage_id = str(payload.get("stage_id") or "").strip()
    if stage_id in _ALLOWED_STAGE_IDS:
        safe_payload["stage_id"] = stage_id
    if event_type in _ALLOWED_TOOL_EVENT_TYPES:
        for key in _ALLOWED_TOOL_KEYS:
            if key not in payload:
                continue
            value = payload[key]
            if key == "duration_ms":
                try:
                    value = max(0, min(3_600_000, int(value)))
                except (TypeError, ValueError):
                    continue
            if key in {"tool_name", "category", "vendor_chain", "status", "result_checksum"}:
                value = str(value)[:160]
            safe_payload[key] = value
    return {
        "sequence": int(event.get("sequence") or 0),
        "event_type": event_type,
        "created_at": _iso(event.get("created_at")),
        "payload": safe_payload,
    }


def _stage_ids_for_market(market: str) -> tuple[str, ...]:
    return _CRYPTO_STAGES if str(market or "").strip().lower() == "crypto" else _STAGES


def build_public_progress(
    *,
    status: str,
    market: str,
    events: Sequence[Mapping[str, Any]] | None,
    artifacts: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Build a deterministic UI progress snapshot from observed callbacks."""

    stage_ids = _stage_ids_for_market(market)
    completed: list[str] = []
    for event in events or ():
        payload = _json_object(event.get("payload_json") or event.get("payload"))
        stage_id = str(payload.get("stage_id") or "").strip()
        if stage_id in stage_ids and stage_id != "report" and stage_id not in completed:
            completed.append(stage_id)

    clean_status = str(status or "queued").strip().lower()
    has_report = any(str(item.get("artifact_name") or "").strip() for item in artifacts or ())
    if clean_status == "succeeded" and has_report:
        completed_with_report = [*completed, "report"] if "report" not in completed else completed
        return {
            "percent": 100,
            "current_stage_id": "report",
            "stage_ids": list(stage_ids),
            "completed_stage_ids": completed_with_report,
            "completed_count": len(completed_with_report),
            "total_count": len(stage_ids),
            "remaining_stage_ids": [],
        }

    next_stage = next((stage for stage in stage_ids if stage not in completed and stage != "report"), "report")
    if clean_status == "queued":
        percent = 0
        next_stage = "initializing"
    else:
        observed_ratio = len(completed) / max(1, len(stage_ids) - 1)
        percent = min(94, max(5, round(5 + observed_ratio * 89)))
        if clean_status == "succeeded":
            percent = min(99, max(percent, 95))
    return {
        "percent": percent,
        "current_stage_id": next_stage,
        "stage_ids": list(stage_ids),
        "completed_stage_ids": completed,
        "completed_count": len(completed),
        "total_count": len(stage_ids),
        "remaining_stage_ids": [stage for stage in stage_ids if stage not in completed],
    }


__all__ = ["build_public_progress", "public_event"]
