"""Refresh the configured economic calendar source and publish it atomically.

The free AkShare/WallstreetCN snapshot is the default. Investing browser
refresh remains opt-in for deployments with permitted access.
"""
import os
import subprocess
from datetime import datetime, timezone

from app.data_providers.economic_calendar import _fetch_akshare_calendar
from app.data_providers.economic_calendar_translation import translate_calendar_event_names
from app.data_providers.investing_calendar_snapshot import (
    REQUIRED_CALENDAR_RANGES, write_investing_calendar_snapshot,
)


def main():
    browser_python = os.getenv('CALENDAR_BROWSER_PYTHON', '/opt/datavest/shared/crypto-insights-venv/bin/python')
    provider = str(os.getenv('ECONOMIC_CALENDAR_PROVIDER', 'akshare_wallstreetcn') or '').strip().lower()
    if provider == 'investing_browser':
        try:
            subprocess.run([browser_python, '-m', 'calendar_worker.investing_calendar_browser', '--once'],
                           timeout=90, check=True)
            return
        except (OSError, subprocess.SubprocessError) as exc:
            print(f'Primary calendar unavailable ({type(exc).__name__}); trying WallstreetCN.', flush=True)
    elif provider not in {'', 'akshare_wallstreetcn', 'wallstreetcn', 'akshare'}:
        raise RuntimeError(f'Unsupported ECONOMIC_CALENDAR_PROVIDER: {provider}')
    else:
        print('Calendar provider configured: AkShare/WallstreetCN; skipping Investing.', flush=True)
    events = translate_calendar_event_names(_fetch_akshare_calendar())
    if not events:
        raise RuntimeError('Both calendar providers unavailable; previous snapshot retained.')
    payload = {
        'source': 'akshare_wallstreetcn',
        'source_url': 'https://wallstreetcn.com/calendar',
        'fallback_from': 'investing_browser' if provider == 'investing_browser' else '',
        'fallback_reason': 'primary_refresh_failed' if provider == 'investing_browser' else 'configured_free_provider',
        'fetched_at': datetime.now(timezone.utc).isoformat(),
        'ranges': list(REQUIRED_CALENDAR_RANGES),
        'events': events,
    }
    write_investing_calendar_snapshot(payload)
    print(f'Calendar imported: {len(events)} events; source=akshare_wallstreetcn', flush=True)


if __name__ == '__main__':
    main()
