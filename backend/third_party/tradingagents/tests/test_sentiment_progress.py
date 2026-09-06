from __future__ import annotations

import time
from threading import Event
from unittest.mock import MagicMock

import pytest

import tradingagents.agents.analysts.sentiment_analyst as sentiment
from tradingagents.agents.schemas import SentimentBand, SentimentReport
from tradingagents.agents.utils.progress import bind_progress_sink


@pytest.mark.unit
def test_sentiment_analysis_publishes_observable_substeps(monkeypatch):
    monkeypatch.setattr(sentiment, "fetch_stocktwits_messages", lambda *a, **k: "stocktwits")
    monkeypatch.setattr(sentiment, "fetch_reddit_posts", lambda *a, **k: "reddit")
    monkeypatch.setattr(sentiment.get_news, "func", lambda *a, **k: "news", raising=False)

    structured = MagicMock()
    structured.invoke.return_value = SentimentReport(
        overall_band=SentimentBand.NEUTRAL,
        overall_score=5.0,
        confidence="medium",
        narrative="Neutral.",
    )
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    events: list[dict[str, object]] = []

    with bind_progress_sink(events.append):
        sentiment.create_sentiment_analyst(llm)({
            "company_of_interest": "BTC-USD",
            "trade_date": "2026-09-05",
            "asset_type": "crypto",
            "messages": [],
        })

    assert [(event["substage_id"], event["status"]) for event in events] == [
        ("news", "started"),
        ("news", "completed"),
        ("stocktwits", "started"),
        ("stocktwits", "completed"),
        ("reddit", "started"),
        ("reddit", "completed"),
        ("ai", "started"),
        ("ai", "completed"),
    ]


@pytest.mark.unit
def test_slow_news_fetch_is_marked_unavailable_and_does_not_block_graph(monkeypatch):
    started = Event()

    def slow_news(*_args, **_kwargs):
        started.set()
        time.sleep(0.2)
        return "late news"

    monkeypatch.setattr(sentiment, "_social_fetch_timeout_seconds", lambda: 0.05)
    monkeypatch.setattr(sentiment.get_news, "func", slow_news, raising=False)
    monkeypatch.setattr(sentiment, "fetch_stocktwits_messages", lambda *a, **k: "stocktwits")
    monkeypatch.setattr(sentiment, "fetch_reddit_posts", lambda *a, **k: "reddit")

    structured = MagicMock()
    structured.invoke.return_value = SentimentReport(
        overall_band=SentimentBand.NEUTRAL,
        overall_score=5.0,
        confidence="low",
        narrative="News source unavailable; other evidence is limited.",
    )
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    events: list[dict[str, object]] = []

    with bind_progress_sink(events.append):
        result = sentiment.create_sentiment_analyst(llm)({
            "company_of_interest": "BTC-USD",
            "trade_date": "2026-09-05",
            "asset_type": "crypto",
            "messages": [],
        })

    assert started.is_set()
    assert result["sentiment_report"]
    assert [(event["substage_id"], event["status"]) for event in events[:2]] == [
        ("news", "started"),
        ("news", "failed"),
    ]
    prompt_text = str(structured.invoke.call_args.args[0])
    assert "news unavailable: timed out" in prompt_text
