import pytest


@pytest.mark.parametrize('value,expected', [('False', False), ('True', True), ('false', False), ('true', True)])
def test_browser_boolean_strings_are_not_truthy(value, expected):
    import asyncio
    from calendar_worker.investing_calendar_browser import select_calendar_range
    class Page:
        async def evaluate(self, script):
            return value
    assert asyncio.run(select_calendar_range(Page(), 'Hôm nay')) is expected


@pytest.mark.parametrize('status,count,want', [('ok',2,'FRESH'),('stale',2,'STALE'),('missing_snapshot',0,'UNAVAILABLE'),('incomplete_snapshot',2,'UNAVAILABLE'),('invalid_snapshot',0,'UNAVAILABLE')])
def test_calendar_freshness_does_not_promote_stale_snapshot(status,count,want):
    from app.data_providers.investing_calendar_snapshot import calendar_freshness
    assert calendar_freshness(status,count) == want


def test_overlapping_ranges_keep_later_published_values():
    from calendar_worker.investing_calendar_browser import deduplicate_rows
    event=dict(date='2026-09-11',time='19:30',country='US',name='CPI',actual='',forecast='2%')
    result=deduplicate_rows([event,dict(event,actual='2.1%'),dict(event,forecast='')])
    assert len(result)==1
    assert result[0]['actual']=='2.1%'
    assert result[0]['forecast']=='2%'


def test_fallback_does_not_copy_previous_into_forecast_and_uses_vietnam_time():
    from app.data_providers.economic_calendar import _normalize_akshare_event
    event = _normalize_akshare_event({'时间': '2026-09-12 00:30:00', '地区': '美国', '事件': 'CPI', '今值': 0, '预期': None, '前值': 2}, 0)
    assert event['forecast'] is None
    assert event['actual'] == '0'
    assert (event['date'], event['time']) == ('2026-09-11', '23:30')


def test_fallback_snapshot_preserves_provider(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from app.data_providers.investing_calendar_snapshot import write_investing_calendar_snapshot, get_investing_calendar_snapshot_payload, REQUIRED_CALENDAR_RANGES
    path = tmp_path / 'calendar.json'
    monkeypatch.setenv('INVESTING_CALENDAR_SNAPSHOT_PATH', str(path))
    write_investing_calendar_snapshot({'source': 'akshare_wallstreetcn', 'source_url': 'https://wallstreetcn.com/calendar', 'fallback_from': 'investing_browser', 'fetched_at': datetime.now(timezone.utc).isoformat(), 'ranges': list(REQUIRED_CALENDAR_RANGES), 'events': [{'name': 'CPI', 'date': '2026-09-11', 'actual': '0', 'forecast': None}]}, path)
    payload = get_investing_calendar_snapshot_payload()
    assert payload['source'] == 'akshare_wallstreetcn'
    assert payload['events'][0]['source'] == 'akshare_wallstreetcn'
    assert payload['events'][0]['forecast'] is None
    assert payload['fallback_from'] == 'investing_browser'


def test_refresh_retains_snapshot_when_both_providers_fail(monkeypatch):
    from calendar_worker import refresh_snapshot as worker
    def fail(*args, **kwargs):
        raise OSError('unavailable')
    monkeypatch.setattr(worker.subprocess, 'run', fail)
    monkeypatch.setattr(worker, '_fetch_akshare_calendar', lambda: [])
    monkeypatch.setattr(worker, 'write_investing_calendar_snapshot', lambda payload: pytest.fail('Must retain last good snapshot'))
    with pytest.raises(RuntimeError, match='previous snapshot retained'):
        worker.main()


def test_refresh_imports_explicit_fallback_in_same_job(monkeypatch):
    from calendar_worker import refresh_snapshot as worker
    def fail(*args, **kwargs):
        raise OSError('unavailable')
    saved = []
    monkeypatch.setattr(worker.subprocess, 'run', fail)
    monkeypatch.setattr(worker, '_fetch_akshare_calendar', lambda: [{'name': 'CPI', 'actual': '0'}])
    monkeypatch.setattr(worker, 'write_investing_calendar_snapshot', saved.append)
    worker.main()
    assert saved[0]['source'] == 'akshare_wallstreetcn'
    assert saved[0]['fallback_from'] == 'investing_browser'
    assert saved[0]['events'][0]['actual'] == '0'
