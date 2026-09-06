"""Honest, lightweight progress signals around the native TradingAgents graph."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from .events import RunEvent


GRAPH_STAGE_IDS = (
    "market",
    "social",
    "news",
    "fundamentals",
    "investment_debate",
    "research_manager",
    "trader",
    "risk_debate",
    "portfolio_manager",
    "report",
)
CRYPTO_STAGE_IDS = tuple(stage for stage in GRAPH_STAGE_IDS if stage != "fundamentals")
PublishProgress = Callable[[str, Mapping[str, Any]], None]


def stage_ids_for_asset_type(asset_type: str) -> tuple[str, ...]:
    return CRYPTO_STAGE_IDS if str(asset_type or "").strip().lower() == "crypto" else GRAPH_STAGE_IDS


@dataclass
class StageProgressTracker:
    """Publish stage lifecycle events without pretending to know LLM completion."""

    asset_type: str
    publish: PublishProgress
    clock: Callable[[], float] = monotonic
    stage_ids: tuple[str, ...] = field(init=False)
    completed_stage_ids: list[str] = field(default_factory=list, init=False)
    current_stage_index: int = field(default=0, init=False)
    stage_started_at: float | None = field(default=None, init=False)
    run_started_at: float | None = field(default=None, init=False)
    heartbeat_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.stage_ids = stage_ids_for_asset_type(self.asset_type)

    @property
    def current_stage_id(self) -> str:
        return self.stage_ids[min(self.current_stage_index, len(self.stage_ids) - 1)]

    def start(self) -> None:
        now = self.clock()
        self.run_started_at = now
        self.stage_started_at = now
        self._publish("stage_started")

    def on_graph_event(self, event: RunEvent) -> None:
        stage_id = str(event.payload.get("stage_id") or "").strip()
        if stage_id not in self.stage_ids or stage_id == "report":
            return
        if stage_id not in self.completed_stage_ids:
            self.completed_stage_ids.append(stage_id)
        next_index = next(
            (index for index, candidate in enumerate(self.stage_ids[:-1]) if candidate not in self.completed_stage_ids),
            len(self.stage_ids) - 1,
        )
        if next_index == self.current_stage_index:
            return
        self.current_stage_index = next_index
        self.stage_started_at = self.clock()
        self._publish("stage_started")

    def heartbeat(self) -> None:
        if self.run_started_at is None or self.stage_started_at is None:
            return
        self.heartbeat_count += 1
        self._publish("stage_heartbeat", include_elapsed=True)

    def _percent(self) -> int:
        denominator = max(1, len(self.stage_ids) - 1)
        return min(94, max(5, round(5 + len(self.completed_stage_ids) / denominator * 89)))

    def _publish(self, event_type: str, *, include_elapsed: bool = False) -> None:
        payload: dict[str, Any] = {
            "stage_id": self.current_stage_id,
            "completed_count": len(self.completed_stage_ids),
            "total_count": len(self.stage_ids),
            "percent": self._percent(),
            "stage_number": self.current_stage_index + 1,
        }
        if include_elapsed:
            now = self.clock()
            payload.update(
                {
                    "elapsed_seconds": max(0, round(now - self.stage_started_at)),
                    "total_elapsed_seconds": max(0, round(now - (self.run_started_at or self.stage_started_at))),
                    "heartbeat_count": self.heartbeat_count,
                }
            )
        self.publish(event_type, payload)


__all__ = ["CRYPTO_STAGE_IDS", "GRAPH_STAGE_IDS", "StageProgressTracker", "stage_ids_for_asset_type"]
