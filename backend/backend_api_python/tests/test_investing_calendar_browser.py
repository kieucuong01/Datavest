"""Contract tests for the Investing browser calendar worker."""
from __future__ import annotations

import asyncio


def test_browser_worker_crawls_every_required_calendar_range():
    from calendar_worker.investing_calendar_browser import (
        REQUIRED_CALENDAR_RANGES,
        select_calendar_range,
    )

    class FakePage:
        def __init__(self):
            self.scripts = []

        async def evaluate(self, script):
            self.scripts.append(script)
            return True

    page = FakePage()
    for label in REQUIRED_CALENDAR_RANGES:
        assert asyncio.run(select_calendar_range(page, label)) is True

    assert REQUIRED_CALENDAR_RANGES == ("Hôm qua", "Hôm nay", "Tuần này", "Tuần tới")
    scripts = "\n".join(page.scripts)
    for label in REQUIRED_CALENDAR_RANGES:
        assert label in scripts


def test_browser_worker_deduplicates_overlapping_range_rows():
    from calendar_worker.investing_calendar_browser import deduplicate_rows

    rows = [
        {"date": "2026-08-31", "time": "09:00", "country": "VN", "name": "Nghỉ lễ Quốc khánh"},
        {"date": "2026-08-31", "time": "09:00", "country": "VN", "name": "Nghỉ lễ Quốc khánh"},
        {"date": "2026-08-31", "time": "20:30", "country": "US", "name": "Niềm tin tiêu dùng"},
    ]

    assert deduplicate_rows(rows) == [rows[0], rows[2]]


def test_browser_worker_decodes_browser_use_json_evaluation_results():
    from calendar_worker.investing_calendar_browser import extract_visible_calendar_rows

    class FakePage:
        async def evaluate(self, script):
            return '[{"date":"2026-08-31","time":"09:00","country":"VN","name":"Sự kiện Việt Nam"}]'

    rows = asyncio.run(extract_visible_calendar_rows(FakePage(), "https://vn.investing.com/economic-calendar/"))
    assert rows[0]["country"] == "VN"
    assert rows[0]["name"] == "Sự kiện Việt Nam"
