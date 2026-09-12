from datetime import datetime
from zoneinfo import ZoneInfo


VN = ZoneInfo("Asia/Ho_Chi_Minh")


def _event(**overrides):
    event = {
        "id": 1,
        "name": "US CPI",
        "name_en": "US CPI",
        "country": "US",
        "date": "2026-09-14",
        "time": "20:30",
        "importance": "high",
        "actual": None,
        "forecast": "0.3%",
    }
    event.update(overrides)
    return event


def test_only_high_events_create_release_checkpoints():
    from calendar_worker.event_scheduler import due_event_checkpoints

    now = datetime(2026, 9, 14, 20, 20, tzinfo=VN)
    due = due_event_checkpoints(
        [_event(), _event(id=2, name="Low event", importance="medium")],
        now=now,
        completed=set(),
    )

    assert len(due) == 1
    assert due[0]["checkpoint"] == "pre_release"
    assert due[0]["event"]["name"] == "US CPI"


def test_actual_value_stops_release_refreshes():
    from calendar_worker.event_scheduler import due_event_checkpoints

    now = datetime(2026, 9, 14, 20, 40, tzinfo=VN)
    assert due_event_checkpoints(
        [_event(actual="0.2%")], now=now, completed=set()
    ) == []


def test_due_checkpoints_are_deduplicated_after_successful_refresh():
    from calendar_worker.event_scheduler import due_event_checkpoints

    now = datetime(2026, 9, 14, 20, 40, tzinfo=VN)
    due = due_event_checkpoints(
        [_event()],
        now=now,
        completed={"2026-09-14|20:30|US|US CPI|pre_release"},
    )

    assert [item["checkpoint"] for item in due] == ["release", "post_5m"]


def test_daily_plan_runs_at_next_five_past_midnight_vietnam_time():
    from calendar_worker.event_scheduler import next_daily_plan_at

    now = datetime(2026, 9, 14, 10, 30, tzinfo=VN)
    assert next_daily_plan_at(now) == datetime(2026, 9, 15, 0, 5, tzinfo=VN)


def test_event_refresh_keeps_cached_labels_without_calling_translation():
    from calendar_worker.refresh_snapshot import merge_cached_event_labels

    existing = [{
        "name": "美国CPI",
        "name_en": "US CPI (MoM)",
        "name_vi": "CPI Hoa Kỳ (theo tháng)",
        "country": "US",
        "date": "2026-09-14",
        "time": "20:30",
    }]
    fresh = [{
        "name": "美国CPI",
        "name_en": "美国CPI",
        "country": "US",
        "date": "2026-09-14",
        "time": "20:30",
        "actual": "0.2%",
    }]

    merged = merge_cached_event_labels(fresh, existing)

    assert merged[0]["name_en"] == "US CPI (MoM)"
    assert merged[0]["name_vi"] == "CPI Hoa Kỳ (theo tháng)"
    assert merged[0]["actual"] == "0.2%"
