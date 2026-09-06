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
_ALLOWED_STAGE_EVENT_TYPES = frozenset({"stage_started", "stage_heartbeat"})
_ALLOWED_STAGE_KEYS = frozenset({
    "stage_id",
    "completed_count",
    "total_count",
    "percent",
    "stage_number",
    "elapsed_seconds",
    "total_elapsed_seconds",
    "heartbeat_count",
})


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
    if event_type in _ALLOWED_TOOL_EVENT_TYPES or event_type in _ALLOWED_STAGE_EVENT_TYPES:
        allowed_keys = _ALLOWED_TOOL_KEYS if event_type in _ALLOWED_TOOL_EVENT_TYPES else _ALLOWED_STAGE_KEYS
        for key in allowed_keys:
            if key not in payload:
                continue
            value = payload[key]
            if key in {"duration_ms", "elapsed_seconds", "total_elapsed_seconds", "heartbeat_count", "completed_count", "total_count", "percent", "stage_number"}:
                try:
                    upper_bound = 3_600_000 if key in {"duration_ms", "elapsed_seconds", "total_elapsed_seconds"} else 10_000
                    value = max(0, min(upper_bound, int(value)))
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
    latest_stage_event: Mapping[str, Any] | None = None
    latest_heartbeat: Mapping[str, Any] | None = None
    latest_stage_start: Mapping[str, Any] | None = None
    for event in events or ():
        payload = _json_object(event.get("payload_json") or event.get("payload"))
        stage_id = str(payload.get("stage_id") or "").strip()
        event_type = str(event.get("event_type") or event.get("kind") or "").strip().lower()
        if event_type == "upstream_chunk" and stage_id in stage_ids and stage_id != "report" and stage_id not in completed:
            completed.append(stage_id)
        if event_type in _ALLOWED_STAGE_EVENT_TYPES and stage_id in stage_ids:
            latest_stage_event = event
            if event_type == "stage_heartbeat":
                latest_heartbeat = event
            else:
                latest_stage_start = event

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
    current_stage = next_stage
    if latest_stage_event:
        current_stage = str(_json_object(latest_stage_event.get("payload_json") or latest_stage_event.get("payload")).get("stage_id") or next_stage)
    if clean_status == "queued":
        percent = 0
        next_stage = "initializing"
        current_stage = next_stage
    else:
        observed_ratio = len(completed) / max(1, len(stage_ids) - 1)
        percent = min(94, max(5, round(5 + observed_ratio * 89)))
        if latest_stage_event:
            stage_payload = _json_object(latest_stage_event.get("payload_json") or latest_stage_event.get("payload"))
            try:
                percent = min(94, max(percent, int(stage_payload.get("percent"))))
            except (TypeError, ValueError):
                pass
        if clean_status == "succeeded":
            percent = min(99, max(percent, 95))
    heartbeat_payload = _json_object((latest_heartbeat or {}).get("payload_json") or (latest_heartbeat or {}).get("payload"))
    heartbeat_stage = str(heartbeat_payload.get("stage_id") or "").strip()
    progress_event = latest_heartbeat if heartbeat_stage == current_stage else (latest_stage_event or {})
    stage_payload = _json_object(progress_event.get("payload_json") or progress_event.get("payload"))
    try:
        elapsed_seconds = max(0, min(3_600_000, int(stage_payload.get("elapsed_seconds", 0))))
    except (TypeError, ValueError):
        elapsed_seconds = 0
    try:
        total_elapsed_seconds = max(0, min(3_600_000, int(stage_payload.get("total_elapsed_seconds", 0))))
    except (TypeError, ValueError):
        total_elapsed_seconds = 0
    started_at = (latest_stage_start or latest_stage_event or {}).get("created_at")
    last_event_at = progress_event.get("created_at")
    try:
        heartbeat_count = max(0, min(10_000, int(stage_payload.get("heartbeat_count", 0))))
    except (TypeError, ValueError):
        heartbeat_count = 0
    return {
        "percent": percent,
        "current_stage_id": current_stage,
        "stage_ids": list(stage_ids),
        "completed_stage_ids": completed,
        "completed_count": len(completed),
        "total_count": len(stage_ids),
        "remaining_stage_ids": [stage for stage in stage_ids if stage not in completed],
        "elapsed_seconds": elapsed_seconds,
        "total_elapsed_seconds": total_elapsed_seconds,
        "stage_started_at": started_at,
        "last_event_at": last_event_at,
        "last_event_type": str(progress_event.get("event_type") or ""),
        "heartbeat_count": heartbeat_count,
    }


__all__ = ["build_public_progress", "public_event"]
