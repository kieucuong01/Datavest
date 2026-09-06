from __future__ import annotations

import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.events import event_from_chunk


def test_native_chunk_progress_event_contains_stage_without_report_payload() -> None:
    event = event_from_chunk(
        "run-123",
        1,
        {"market_report": "private report body", "data": {"secret": "not for browser"}},
    )

    assert event.payload == {"stage_id": "market", "completed_stage_ids": ["market"]}


def test_values_stream_ignores_empty_reports_and_tracks_all_completed_stages():
    initial = {"market_report": "", "sentiment_report": "", "news_report": "", "fundamentals_report": ""}
    assert event_from_chunk("run", 1, initial).payload["completed_stage_ids"] == []
    cumulative = {**initial, "market_report": "market", "sentiment_report": "social", "news_report": "news"}
    event = event_from_chunk("run", 2, cumulative)
    assert event.payload["stage_id"] == "news"
    assert event.payload["completed_stage_ids"] == ["market", "social", "news"]


def test_partial_debate_is_not_counted_as_finished():
    chunk = {"market_report": "market", "investment_debate_state": {"bull_history": "first response"}}
    assert "investment_debate" not in event_from_chunk("run", 1, chunk).payload["completed_stage_ids"]
    chunk["investment_debate_state"]["judge_decision"] = "decision"
    assert event_from_chunk("run", 2, chunk).payload["completed_stage_ids"][-2:] == ["investment_debate", "research_manager"]
