"""Event-driven scheduler for economic-calendar refreshes.

The provider is fetched for daily discovery and an infrequent safety guard.
High-importance events receive short refresh windows around their scheduled
release time so actual values can arrive quickly without polling the whole
calendar every 30 minutes.
"""
from __future__ import annotations

import json
import os
import signal
import tempfile
import time
from datetime import datetime, time as clock_time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set
from zoneinfo import ZoneInfo

from calendar_worker.refresh_snapshot import refresh_calendar_snapshot

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DEFAULT_STATE_PATH = "data/economic-calendar/event-schedule.json"
DEFAULT_GUARD_INTERVAL_SECONDS = 21600
DEFAULT_RETRY_SECONDS = 300
CHECKPOINTS = (
    ("pre_release", -15),
    ("release", 0),
    ("post_5m", 5),
    ("post_15m", 15),
    ("post_30m", 30),
    ("post_60m", 60),
)


def _as_vietnam_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(VIETNAM_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=VIETNAM_TZ)
    return value.astimezone(VIETNAM_TZ)


def _event_key(event: Dict[str, Any]) -> str:
    return "|".join((
        str(event.get("date") or "").strip(),
        str(event.get("time") or "").strip(),
        str(event.get("country") or "").strip().upper(),
        str(event.get("name") or event.get("event") or "").strip(),
    ))


def _has_actual(event: Dict[str, Any]) -> bool:
    value = event.get("actual")
    return value is not None and str(value).strip() not in {"", "-", "—", "–"}


def _scheduled_at(event: Dict[str, Any]) -> datetime | None:
    date_value = str(event.get("date") or "").strip()
    time_value = str(event.get("time") or "").strip()
    if not date_value or len(time_value) != 5 or time_value == "--:--":
        return None
    try:
        parsed = datetime.combine(
            datetime.strptime(date_value, "%Y-%m-%d").date(),
            clock_time.fromisoformat(time_value),
        )
    except ValueError:
        return None
    return parsed.replace(tzinfo=VIETNAM_TZ)


def _checkpoints_for(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    if str(event.get("importance") or "").strip().lower() not in {"high", "critical"}:
        return []
    scheduled_at = _scheduled_at(event)
    if scheduled_at is None:
        return []
    event_key = _event_key(event)
    return [
        {
            "key": f"{event_key}|{label}",
            "event": event,
            "checkpoint": label,
            "at": scheduled_at + timedelta(minutes=offset),
        }
        for label, offset in CHECKPOINTS
    ]


def due_event_checkpoints(
    events: Iterable[Dict[str, Any]],
    *,
    now: datetime | None = None,
    completed: Set[str] | None = None,
) -> List[Dict[str, Any]]:
    """Return due high-importance checkpoints not completed after a refresh."""
    current = _as_vietnam_time(now)
    completed_keys = completed or set()
    due = [
        checkpoint
        for event in events
        if isinstance(event, dict) and not _has_actual(event)
        for checkpoint in _checkpoints_for(event)
        if checkpoint["at"] <= current and checkpoint["key"] not in completed_keys
    ]
    return sorted(due, key=lambda item: item["at"])


def next_daily_plan_at(now: datetime | None = None) -> datetime:
    current = _as_vietnam_time(now)
    candidate = current.replace(hour=0, minute=5, second=0, microsecond=0)
    return candidate if current < candidate else candidate + timedelta(days=1)


def _state_path() -> Path:
    return Path(os.getenv("CALENDAR_EVENT_SCHEDULE_PATH", DEFAULT_STATE_PATH)).expanduser()


def _read_state(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        Path(temporary_name).replace(path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _seconds(name: str, default: int) -> int:
    try:
        return max(60, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _now() -> datetime:
    return datetime.now(VIETNAM_TZ)


def _load_events_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    events = payload.get("events") if isinstance(payload, dict) else []
    return [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []


def run() -> None:
    state_path = _state_path()
    state = _read_state(state_path)
    completed = set(str(item) for item in state.get("completed", []) if item)
    last_plan = _now()
    last_guard = last_plan
    last_event_attempt: datetime | None = None
    events: List[Dict[str, Any]] = []
    stopping = False

    def stop(*_args: Any) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def refresh(reason: str, translate: bool) -> None:
        nonlocal events, last_plan, last_guard
        payload = refresh_calendar_snapshot(translate=translate, reason=reason)
        events = _load_events_from_payload(payload)
        now = _now()
        if reason in {"startup", "daily_plan"}:
            last_plan = now
        if reason in {"startup", "guard", "daily_plan"}:
            last_guard = now
        _write_state(state_path, {
            "version": 1,
            "updated_at": now.isoformat(),
            "last_plan_at": last_plan.isoformat(),
            "last_guard_at": last_guard.isoformat(),
            "completed": sorted(completed),
            "important_events": [
                {"key": _event_key(event), "scheduled_at": _scheduled_at(event).isoformat()}
                for event in events
                if _checkpoints_for(event)
            ],
        })

    guard_interval = _seconds("CALENDAR_EVENT_GUARD_INTERVAL_SECONDS", DEFAULT_GUARD_INTERVAL_SECONDS)
    retry_seconds = _seconds("CALENDAR_EVENT_RETRY_SECONDS", DEFAULT_RETRY_SECONDS)

    def safe_refresh(reason: str, translate: bool) -> bool:
        try:
            refresh(reason, translate)
            return True
        except Exception as exc:
            print(f"Calendar refresh failed; reason={reason}; error={type(exc).__name__}", flush=True)
            return False

    while not safe_refresh("startup", True) and not stopping:
        time.sleep(retry_seconds)

    while not stopping:
        now = _now()
        daily_due = now >= next_daily_plan_at(last_plan)
        guard_due = (now - last_guard).total_seconds() >= guard_interval
        due = due_event_checkpoints(events, now=now, completed=completed)
        event_retry_ready = last_event_attempt is None or (now - last_event_attempt).total_seconds() >= retry_seconds

        if daily_due:
            previous_completed = set(completed)
            completed.clear()
            if not safe_refresh("daily_plan", True):
                completed.update(previous_completed)
                time.sleep(retry_seconds)
            continue
        if guard_due:
            if not safe_refresh("guard", True):
                time.sleep(retry_seconds)
            continue
        if due and event_retry_ready:
            last_event_attempt = now
            if safe_refresh("important_event", False):
                completed.update(item["key"] for item in due)
            continue

        future_checkpoints = [
            item["at"] for event in events if isinstance(event, dict) and not _has_actual(event)
            for item in _checkpoints_for(event) if item["key"] not in completed and item["at"] > now
        ]
        next_wake = min(
            [next_daily_plan_at(last_plan), last_guard + timedelta(seconds=guard_interval), *future_checkpoints],
            default=now + timedelta(seconds=60),
        )
        time.sleep(max(1, min(60, (next_wake - now).total_seconds())))


def main() -> None:
    run()


if __name__ == "__main__":
    main()
