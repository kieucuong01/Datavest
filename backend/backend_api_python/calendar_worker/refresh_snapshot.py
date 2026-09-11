"""Bounded browser refresh; publish an explicitly labelled free fallback on failure."""
import os
import subprocess
from datetime import datetime, timezone

from app.data_providers.economic_calendar import _fetch_akshare_calendar
from app.data_providers.investing_calendar_snapshot import (
    REQUIRED_CALENDAR_RANGES, write_investing_calendar_snapshot,
)


def main():
    browser_python = os.getenv('CALENDAR_BROWSER_PYTHON', '/opt/datavest/shared/crypto-insights-venv/bin/python')
    try:
        subprocess.run([browser_python, '-m', 'calendar_worker.investing_calendar_browser', '--once'],
                       timeout=90, check=True)
        return
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'Primary calendar unavailable ({type(exc).__name__}); trying WallstreetCN.', flush=True)
    events = _fetch_akshare_calendar()
    if not events:
        raise RuntimeError('Both calendar providers unavailable; previous snapshot retained.')
    payload = {
        'source': 'akshare_wallstreetcn',
        'source_url': 'https://wallstreetcn.com/calendar',
        'fallback_from': 'investing_browser',
        'fallback_reason': 'primary_refresh_failed',
        'fetched_at': datetime.now(timezone.utc).isoformat(),
        'ranges': list(REQUIRED_CALENDAR_RANGES),
        'events': events,
    }
    write_investing_calendar_snapshot(payload)
    print(f'Calendar imported: {len(events)} events; source=akshare_wallstreetcn', flush=True)


if __name__ == '__main__':
    main()
