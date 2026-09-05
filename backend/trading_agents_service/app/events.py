"""Ordered, JSON-safe event records derived from native LangGraph chunks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


_CHUNK_STAGE_KEYS = (
    ("market_report", "market"),
    ("sentiment_report", "social"),
    ("news_report", "news"),
    ("fundamentals_report", "fundamentals"),
    ("investment_debate_state", "investment_debate"),
    ("investment_plan", "research_manager"),
    ("trader_investment_plan", "trader"),
    ("risk_debate_state", "risk_debate"),
    ("final_trade_decision", "portfolio_manager"),
)


@dataclass(frozen=True)
class RunEvent:
    run_id: str
    sequence: int
    kind: str
    payload: dict[str, JsonValue]


def _json_value(value: Any) -> JsonValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_value(model_dump())
    return str(value)


def event_from_chunk(run_id: str, sequence: int, chunk: Mapping[str, Any]) -> RunEvent:
    stage_id = next((stage for key, stage in _CHUNK_STAGE_KEYS if key in chunk), None)
    return RunEvent(
        run_id=run_id,
        sequence=sequence,
        kind="upstream_chunk",
        payload={"stage_id": stage_id} if stage_id else {},
    )
