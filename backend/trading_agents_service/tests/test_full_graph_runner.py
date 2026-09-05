from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.runner import FULL_UPSTREAM_ROLES, TradingAgentsRunRequest, run_full_graph


class _FakePropagator:
    def create_initial_state(
        self,
        ticker: str,
        analysis_date: str,
        *,
        asset_type: str,
        instrument_context: str,
    ) -> dict[str, str]:
        return {
            "company_of_interest": ticker,
            "trade_date": analysis_date,
            "asset_type": asset_type,
            "instrument_context": instrument_context,
        }

    def get_graph_args(self) -> dict[str, Any]:
        return {"stream_mode": "values", "config": {"recursion_limit": 100}}


class _FakeCompiledGraph:
    def __init__(self, owner: "_FakeUpstreamGraph") -> None:
        self._owner = owner

    def stream(self, graph_input: dict[str, str], **kwargs: Any):
        self._owner.calls.append("stream")
        self._owner.graph_input = graph_input
        self._owner.graph_args = kwargs
        yield {"market_report": "verified market report"}
        yield {
            "final_trade_decision": "Hold",
            "risk_debate_state": {"judge_decision": "Hold"},
        }


class _FakeUpstreamGraph:
    def __init__(self, *, selected_analysts: tuple[str, ...], config: dict[str, Any]) -> None:
        self.selected_analysts = selected_analysts
        self.config = config
        self.calls: list[str] = []
        self.graph_input: dict[str, str] | None = None
        self.graph_args: dict[str, Any] | None = None
        self.propagator = _FakePropagator()
        self.graph = _FakeCompiledGraph(self)

    def resolve_instrument_context(self, ticker: str, asset_type: str) -> str:
        self.calls.append("resolve_instrument_context")
        return f"{ticker}:{asset_type}"

    def begin_checkpoint(self, ticker: str, analysis_date: str, asset_type: str) -> str:
        self.calls.append("begin_checkpoint")
        return "checkpoint-thread"

    def checkpoint_input(self, initial_state: dict[str, str]) -> dict[str, str]:
        self.calls.append("checkpoint_input")
        return initial_state

    def clear_checkpoint_on_success(self, ticker: str, analysis_date: str, asset_type: str) -> None:
        self.calls.append("clear_checkpoint_on_success")

    def end_checkpoint(self) -> None:
        self.calls.append("end_checkpoint")

    def save_reports(self, final_state: dict[str, Any], ticker: str, save_path: Path) -> Path:
        self.calls.append("save_reports")
        save_path.mkdir(parents=True, exist_ok=True)
        report = save_path / "complete_report.md"
        report.write_text(final_state["final_trade_decision"], encoding="utf-8")
        return report


def test_full_run_uses_every_upstream_role_and_native_lifecycle(tmp_path: Path) -> None:
    created: list[_FakeUpstreamGraph] = []

    def graph_factory(*, selected_analysts: tuple[str, ...], config: dict[str, Any]) -> _FakeUpstreamGraph:
        graph = _FakeUpstreamGraph(selected_analysts=selected_analysts, config=config)
        created.append(graph)
        return graph

    request = TradingAgentsRunRequest(
        run_id="run-123",
        user_id="user-a",
        ticker="BTC-USD",
        asset_type="crypto",
        analysis_date="2026-09-05",
        native_config={"checkpoint_enabled": True},
    )

    result = run_full_graph(request, state_root=tmp_path, graph_factory=graph_factory)

    graph = created[0]
    assert set(result.executed_roles) == set(FULL_UPSTREAM_ROLES)
    assert graph.selected_analysts == ("market", "social", "news", "fundamentals")
    assert graph.config["results_dir"].startswith(str(tmp_path))
    assert graph.config["data_cache_dir"].startswith(str(tmp_path))
    assert graph.config["memory_log_path"].startswith(str(tmp_path))
    assert graph.graph_args == {
        "stream_mode": "values",
        "config": {"recursion_limit": 100, "configurable": {"thread_id": "checkpoint-thread"}},
    }
    assert graph.calls == [
        "resolve_instrument_context",
        "begin_checkpoint",
        "checkpoint_input",
        "stream",
        "clear_checkpoint_on_success",
        "end_checkpoint",
        "save_reports",
    ]
    assert [event.sequence for event in result.events] == [1, 2]
    assert result.artifact.path.name == "complete_report.md"
    assert result.artifact.sha256
