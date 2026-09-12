"""Refresh the configured economic calendar source and publish it atomically.

The free AkShare/WallstreetCN snapshot is the default. Investing browser
refresh remains opt-in for deployments with permitted access.
"""
import os
import subprocess
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.data_providers.economic_calendar import _fetch_akshare_calendar
from app.data_providers.economic_calendar_translation import translate_calendar_event_names
from app.data_providers.investing_calendar_snapshot import (
    REQUIRED_CALENDAR_RANGES, snapshot_path, write_investing_calendar_snapshot,
)


def _event_label_key(event: Dict[str, Any]) -> tuple[str, str, str, str]:
    """Build a stable identity without using translated labels."""
    return (
        str(event.get("date") or "").strip(),
        str(event.get("time") or "").strip(),
        str(event.get("country") or "").strip().upper(),
        str(event.get("name") or event.get("event") or "").strip().lower(),
    )


def _read_existing_events() -> List[Dict[str, Any]]:
    path = snapshot_path("akshare_wallstreetcn")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    events = payload.get("events") if isinstance(payload, dict) else []
    return [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []


def merge_cached_event_labels(
    events: Iterable[Dict[str, Any]], existing_events: Iterable[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Keep translated labels while a release refresh updates numeric values."""
    cached = {
        _event_label_key(event): event
        for event in existing_events
        if isinstance(event, dict) and _event_label_key(event)[3]
    }
    merged: List[Dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        current = dict(event)
        previous = cached.get(_event_label_key(current))
        if previous:
            for field in ("name_vi", "name_en"):
                if previous.get(field):
                    current[field] = previous[field]
        merged.append(current)
    return merged


def refresh_calendar_snapshot(*, translate: bool = True, reason: str = "scheduled") -> Dict[str, Any]:
    """Fetch and publish one calendar snapshot.

    Release-time refreshes deliberately skip translation: they only need to
    update actual/forecast quickly. The daily planner and guard refreshes may
    enrich new labels through the existing cached translation worker.
    """
    browser_python = os.getenv("CALENDAR_BROWSER_PYTHON", "/opt/datavest/shared/crypto-insights-venv/bin/python")
    provider = str(os.getenv("ECONOMIC_CALENDAR_PROVIDER", "akshare_wallstreetcn") or "").strip().lower()
    fallback_from = ""
    if provider == "investing_browser":
        try:
            subprocess.run(
                [browser_python, "-m", "calendar_worker.investing_calendar_browser", "--once"],
                timeout=90,
                check=True,
            )
            path = snapshot_path("investing_browser")
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            print(f"Primary calendar unavailable ({type(exc).__name__}); trying WallstreetCN.", flush=True)
            fallback_from = "investing_browser"
            provider = "akshare_wallstreetcn"
    elif provider not in {"", "akshare_wallstreetcn", "wallstreetcn", "akshare"}:
        raise RuntimeError(f"Unsupported ECONOMIC_CALENDAR_PROVIDER: {provider}")
    else:
        print("Calendar provider configured: AkShare/WallstreetCN; skipping Investing.", flush=True)

    events = _fetch_akshare_calendar()
    if translate:
        events = translate_calendar_event_names(events)
    else:
        events = merge_cached_event_labels(events, _read_existing_events())
    if not events:
        raise RuntimeError("Both calendar providers unavailable; previous snapshot retained.")
    payload = {
        "source": "akshare_wallstreetcn",
        "source_url": "https://wallstreetcn.com/calendar",
        "fallback_from": fallback_from,
        "fallback_reason": "primary_refresh_failed" if fallback_from else "configured_free_provider",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ranges": list(REQUIRED_CALENDAR_RANGES),
        "refresh_reason": reason,
        "events": events,
    }
    write_investing_calendar_snapshot(payload)
    print(f"Calendar imported: {len(events)} events; source=akshare_wallstreetcn; reason={reason}", flush=True)
    return payload


def main():
    refresh_calendar_snapshot(translate=True, reason="manual")


if __name__ == '__main__':
    main()
