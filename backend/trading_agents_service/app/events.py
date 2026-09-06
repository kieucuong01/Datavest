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
    # stream_mode='values' includes EVERY state field, including empty reports
    # and old reports. Presence/first-key detection leaves the UI stuck at social.
    completed = [stage for key, stage in _CHUNK_STAGE_KEYS
                 if key not in {"investment_debate_state", "risk_debate_state"}
                 and isinstance(chunk.get(key), str) and chunk[key].strip()]
    investment = chunk.get("investment_debate_state") or {}
    risk = chunk.get("risk_debate_state") or {}
    if isinstance(investment, Mapping) and investment.get("judge_decision"):
        completed.extend(["investment_debate", "research_manager"])
    elif chunk.get("investment_plan"):
        completed.append("investment_debate")
    if isinstance(risk, Mapping) and risk.get("judge_decision"):
        completed.extend(["risk_debate", "portfolio_manager"])
    elif chunk.get("final_trade_decision"):
        completed.append("risk_debate")
    ordered = [stage for _, stage in _CHUNK_STAGE_KEYS if stage in completed]
    stage_id = ordered[-1] if ordered else None
    return RunEvent(
        run_id=run_id,
        sequence=sequence,
        kind="upstream_chunk",
        payload={"stage_id": stage_id, "completed_stage_ids": ordered},
    )
