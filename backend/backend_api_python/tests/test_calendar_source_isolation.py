import json
from datetime import datetime, timezone

from app.data_providers.investing_calendar_snapshot import (
    get_investing_calendar_snapshot_payload, write_investing_calendar_snapshot,
    REQUIRED_CALENDAR_RANGES,
)


def payload(source, name):
    return dict(source=source, ranges=list(REQUIRED_CALENDAR_RANGES),
                fetched_at=datetime.now(timezone.utc).isoformat(),
                events=[dict(name=name, country='VN', date='2026-09-12', actual='0')])


def test_backup_writer_cannot_overwrite_vietnam_investing_events(monkeypatch, tmp_path):
    path = tmp_path / 'investing-browser.json'
    monkeypatch.setenv('INVESTING_CALENDAR_SNAPSHOT_PATH', str(path))
    write_investing_calendar_snapshot(payload('investing_browser', 'CPI Việt Nam'))
    original = path.read_bytes()
    write_investing_calendar_snapshot(payload('akshare_wallstreetcn', '备用事件'))
    assert path.read_bytes() == original
    assert get_investing_calendar_snapshot_payload()['events'][0]['name'] == 'CPI Việt Nam'
    assert get_investing_calendar_snapshot_payload(source='akshare_wallstreetcn')['events'][0]['name'] == '备用事件'


def test_legacy_mixed_file_is_never_presented_as_primary(monkeypatch, tmp_path):
    path = tmp_path / 'investing-browser.json'
    path.write_text(json.dumps(payload('akshare_wallstreetcn', '备用事件')), encoding='utf-8')
    monkeypatch.setenv('INVESTING_CALENDAR_SNAPSHOT_PATH', str(path))
    primary = get_investing_calendar_snapshot_payload()
    assert primary['events'] == []
    assert primary['status'] == 'source_mismatch'
    backup = get_investing_calendar_snapshot_payload(source='akshare_wallstreetcn')
    assert backup['events'][0]['name'] == '备用事件'
