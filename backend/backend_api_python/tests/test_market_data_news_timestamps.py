from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.market_data_collector import MarketDataCollector
from app.services import market_data_collector as collector_module


class _FakeFinnhubClient:
    def __init__(self, timestamp: int) -> None:
        self.timestamp = timestamp

    def company_news(self, *_args, **_kwargs):
        return [{
            "datetime": self.timestamp,
            "headline": "Confirmed company update",
            "summary": "A timestamp conversion fixture.",
            "source": "Finnhub",
            "url": "https://example.test/news",
        }]


def test_finnhub_unix_timestamp_is_utc_when_server_uses_asia_shanghai(monkeypatch):
    expected = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    collector = MarketDataCollector.__new__(MarketDataCollector)
    collector._finnhub_client = _FakeFinnhubClient(int(expected.timestamp()))
    collector._get_news_from_search = lambda *_args, **_kwargs: []
    collector._get_global_major_events = lambda: []
    monkeypatch.setenv("FINNHUB_FREE_ONLY", "true")

    class ShanghaiDatetime(datetime):
        @classmethod
        def fromtimestamp(cls, timestamp, tz=None):
            if tz is None:
                return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None) + timedelta(hours=8)
            return datetime.fromtimestamp(timestamp, tz)

    monkeypatch.setattr(collector_module, "datetime", ShanghaiDatetime)
    result = collector._get_news("USStock", "TSLA")

    assert result["news"][0]["datetime"] == "2026-09-08T12:00:00Z"


@pytest.mark.parametrize("timestamp", ["invalid", float("inf"), 10**30])
def test_invalid_news_timestamp_keeps_headline_without_inventing_date(monkeypatch, timestamp):
    collector = MarketDataCollector.__new__(MarketDataCollector)
    collector._finnhub_client = _FakeFinnhubClient(timestamp)
    collector._get_news_from_search = lambda *_args, **_kwargs: []
    collector._get_global_major_events = lambda: []
    monkeypatch.setenv("FINNHUB_FREE_ONLY", "true")

    result = collector._get_news("USStock", "TSLA")

    assert result["news"][0]["headline"] == "Confirmed company update"
    assert result["news"][0]["datetime"] == ""


def test_mixed_news_sources_are_sorted_by_instant_before_truncation(monkeypatch):
    collector = MarketDataCollector.__new__(MarketDataCollector)
    collector._finnhub_client = _FakeFinnhubClient(int(datetime(2026, 9, 8, 12, tzinfo=timezone.utc).timestamp()))
    later_local = datetime(2026, 9, 8, 14, tzinfo=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    collector._get_news_from_search = lambda *_args, **_kwargs: [
        {"headline": "Later search update", "datetime": later_local},
        {"headline": "Unknown date", "datetime": "invalid"},
    ]
    collector._get_global_major_events = lambda: [
        {"headline": "Latest global event", "datetime": "2026-09-08T23:00:00+08:00"},
    ]
    monkeypatch.setenv("FINNHUB_FREE_ONLY", "true")

    result = collector._get_news("USStock", "TSLA")

    assert [item["headline"] for item in result["news"]] == [
        "Latest global event", "Later search update", "Confirmed company update", "Unknown date",
    ]
