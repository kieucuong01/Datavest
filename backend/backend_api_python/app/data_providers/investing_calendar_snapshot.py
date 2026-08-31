"""Read the calendar snapshot produced by the Investing browser worker.

The API only reads a local snapshot: browser automation remains a separate,
scheduled process so normal dashboard requests never scrape an upstream site.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


DEFAULT_SNAPSHOT_PATH = "data/economic-calendar/investing-browser.json"
DEFAULT_STALE_AFTER_SECONDS = 7200
SOURCE_URL = "https://vn.investing.com/economic-calendar/"
REQUIRED_CALENDAR_RANGES = ("Hôm qua", "Hôm nay", "Tuần này", "Tuần tới")

_COUNTRIES = {
    "united states": "US", "hoa kỳ": "US", "mỹ": "US", "us": "US",
    "vietnam": "VN", "việt nam": "VN", "vn": "VN",
    "united kingdom": "UK", "vương quốc anh": "UK", "uk": "UK",
    "euro zone": "EU", "eurozone": "EU", "khu vực đồng euro": "EU", "eu": "EU",
}


def snapshot_path() -> Path:
    return Path(os.getenv("INVESTING_CALENDAR_SNAPSHOT_PATH", DEFAULT_SNAPSHOT_PATH)).expanduser()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value if value and value not in {"-", "—", "–"} else None


def _country(value: Any) -> str:
    text = (_text(value) or "INTL").upper()
    if len(text) == 2 and text.isalpha():
        return text
    return _COUNTRIES.get(text.lower(), "INTL")


def _importance(value: Any) -> str:
    raw = str(value or "").lower()
    if raw in {"3", "4", "high", "critical"}:
        return "high"
    if raw in {"1", "low"}:
        return "low"
    return "medium"


def normalize_investing_events(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    """Normalize only fields rendered in Investing's calendar table."""
    events: List[Dict[str, Any]] = []
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        name = _text(row.get("name") or row.get("event"))
        date = _text(row.get("date"))
        if not name or not date:
            continue
        events.append({
            "id": _text(row.get("id")) or f"investing-{date}-{_text(row.get('time')) or 'all'}-{_country(row.get('country'))}-{index}",
            "name": name,
            "name_en": _text(row.get("name_en") or row.get("event_en")),
            "country": _country(row.get("country")),
            "date": date[:10],
            "time": _text(row.get("time")),
            "importance": _importance(row.get("importance")),
            "actual": _text(row.get("actual")),
            "forecast": _text(row.get("forecast")),
            "previous": _text(row.get("previous")),
            "is_released": bool(_text(row.get("actual"))),
            "source": "investing_browser",
            "source_url": _text(row.get("source_url")) or SOURCE_URL,
        })
    return events


def write_investing_calendar_snapshot(payload: Dict[str, Any], path: Path | None = None) -> Path:
    """Atomically publish a worker payload so readers never see partial JSON."""
    target = path or snapshot_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        Path(temporary_name).replace(target)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink(missing_ok=True)
    return target


def _age_seconds(fetched_at: Any) -> float | None:
    try:
        parsed = datetime.fromisoformat(str(fetched_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds())


def get_investing_calendar_snapshot_payload() -> Dict[str, Any]:
    path = snapshot_path()
    if not path.is_file():
        return {
            "events": [], "status": "missing_snapshot", "source": "investing_browser",
            "config_key": "INVESTING_CALENDAR_SNAPSHOT_PATH",
            "message": "Investing browser calendar snapshot has not been created yet.",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "events": [], "status": "invalid_snapshot", "source": "investing_browser",
            "config_key": "INVESTING_CALENDAR_SNAPSHOT_PATH", "message": str(exc),
        }
    if not isinstance(payload, dict):
        payload = {}
    fetched_at = payload.get("fetched_at")
    ranges = tuple(str(item).strip() for item in payload.get("ranges", []) if str(item).strip())
    complete = set(REQUIRED_CALENDAR_RANGES).issubset(ranges)
    stale_after = max(60, int(os.getenv("INVESTING_CALENDAR_STALE_AFTER_SECONDS", DEFAULT_STALE_AFTER_SECONDS)))
    age = _age_seconds(fetched_at)
    return {
        "events": normalize_investing_events(payload.get("events", [])) if complete else [],
        "status": "incomplete_snapshot" if not complete else ("stale" if age is None or age > stale_after else "ok"),
        "source": "investing_browser",
        "source_url": payload.get("source_url") or SOURCE_URL,
        "last_success_at": fetched_at or "",
        "ranges": list(ranges),
        "config_key": "INVESTING_CALENDAR_SNAPSHOT_PATH",
        "message": (
            "Calendar snapshot does not contain all required ranges."
            if not complete else
            ("Calendar snapshot is older than its refresh window." if age is None or age > stale_after else "")
        ),
    }
