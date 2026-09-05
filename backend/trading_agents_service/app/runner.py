"""Thin adapter that executes the complete, unmodified TradingAgents graph."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .events import RunEvent, event_from_chunk
from .reporting import RunArtifact, save_native_report
from .state import UserStatePaths, require_safe_identifier, resolve_user_state
from .upstream_config import NativeToolEvent, NativeToolObserver


FULL_ANALYST_SELECTION = ("market", "social", "news", "fundamentals")
FULL_UPSTREAM_ROLES = (
    "market",
    "social",
    "news",
    "fundamentals",
    "bull",
    "bear",
    "research_manager",
    "trader",
    "aggressive",
    "neutral",
    "conservative",
    "portfolio_manager",
)
_SUPPORTED_ASSET_TYPES = frozenset({"stock", "crypto"})


class RunRequestError(ValueError):
    """Raised when an internal run request cannot safely run the full graph."""


@dataclass(frozen=True)
class TradingAgentsRunRequest:
    run_id: str
    user_id: str
    ticker: str
    asset_type: str
    analysis_date: str
    selected_analysts: tuple[str, ...] = FULL_ANALYST_SELECTION
    native_config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradingAgentsRunResult:
    events: tuple[RunEvent, ...]
    tool_events: tuple[NativeToolEvent, ...]
    artifact: RunArtifact
    executed_roles: tuple[str, ...]
    final_state: dict[str, Any]


GraphFactory = Callable[..., Any]


def _validate_request(request: TradingAgentsRunRequest) -> None:
    try:
        require_safe_identifier(request.run_id, field="run_id")
        require_safe_identifier(request.user_id, field="user_id")
    except ValueError as error:
        raise RunRequestError(str(error)) from error
    if not isinstance(request.ticker, str) or not request.ticker.strip():
        raise RunRequestError("ticker is required")
    if request.asset_type not in _SUPPORTED_ASSET_TYPES:
        raise RunRequestError("asset_type must be stock or crypto")
    try:
        date.fromisoformat(request.analysis_date)
    except (TypeError, ValueError) as error:
        raise RunRequestError("analysis_date must be an ISO date") from error
    if tuple(request.selected_analysts) != FULL_ANALYST_SELECTION:
        raise RunRequestError("the private runtime always executes all TradingAgents analysts")
    if not isinstance(request.native_config, Mapping):
        raise RunRequestError("native_config must be a mapping")


def _default_graph_factory(
    *,
    selected_analysts: tuple[str, ...],
    config: dict[str, Any],
    callbacks: list[Any],
) -> Any:
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    return TradingAgentsGraph(
        selected_analysts=selected_analysts,
        config=config,
        callbacks=callbacks,
    )


def _effective_analysts(asset_type: str) -> tuple[str, ...]:
    """Use TradingAgents' own asset-mode filter instead of a DataVest variant."""

    from cli.models import AnalystType, AssetType
    from cli.utils import filter_analysts_for_asset_type

    analysts = [
        AnalystType.MARKET,
        AnalystType.SOCIAL,
        AnalystType.NEWS,
        AnalystType.FUNDAMENTALS,
    ]
    return tuple(
        analyst.value
        for analyst in filter_analysts_for_asset_type(analysts, AssetType(asset_type))
    )


def _executed_roles(selected_analysts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        role
        for role in FULL_UPSTREAM_ROLES
        if role != "fundamentals" or "fundamentals" in selected_analysts
    )


def _native_config(request: TradingAgentsRunRequest, paths: UserStatePaths) -> dict[str, Any]:
    """Apply caller-native settings while retaining service-owned file paths."""

    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config.update(request.native_config)
    config.update(
        {
            "results_dir": str(paths.results_dir),
            "data_cache_dir": str(paths.data_cache_dir),
            "memory_log_path": str(paths.memory_log_path),
        }
    )
    return config


def _merge_chunks(chunks: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Match the upstream CLI's state-delta merge behavior exactly."""

    final_state: dict[str, Any] = {}
    for chunk in chunks:
        final_state.update(chunk)
    return final_state


def run_full_graph(
    request: TradingAgentsRunRequest,
    *,
    state_root: str | Path,
    graph_factory: GraphFactory | None = None,
) -> TradingAgentsRunResult:
    """Run every upstream role without replacing agent prompts, nodes or tools."""

    _validate_request(request)
    paths = resolve_user_state(state_root, request.user_id)
    paths.create_directories()
    native_config = _native_config(request, paths)
    tool_observer = NativeToolObserver(native_config)
    callbacks = [tool_observer]
    selected_analysts = _effective_analysts(request.asset_type)
    graph = (graph_factory or _default_graph_factory)(
        selected_analysts=selected_analysts,
        config=native_config,
        callbacks=callbacks,
    )

    instrument_context = graph.resolve_instrument_context(request.ticker, request.asset_type)
    initial_state = graph.propagator.create_initial_state(
        request.ticker,
        request.analysis_date,
        asset_type=request.asset_type,
        instrument_context=instrument_context,
    )
    graph_args = graph.propagator.get_graph_args(callbacks=callbacks)
    chunks: list[Mapping[str, Any]] = []
    events: list[RunEvent] = []

    try:
        checkpoint_thread_id = graph.begin_checkpoint(
            request.ticker,
            request.analysis_date,
            request.asset_type,
        )
        if checkpoint_thread_id is not None:
            graph_args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = checkpoint_thread_id

        for sequence, chunk in enumerate(
            graph.graph.stream(graph.checkpoint_input(initial_state), **graph_args),
            start=1,
        ):
            chunks.append(chunk)
            events.append(event_from_chunk(request.run_id, sequence, chunk))

        graph.clear_checkpoint_on_success(
            request.ticker,
            request.analysis_date,
            request.asset_type,
        )
    finally:
        graph.end_checkpoint()

    final_state = _merge_chunks(chunks)
    artifact = save_native_report(
        graph,
        final_state=final_state,
        ticker=request.ticker,
        run_id=request.run_id,
        paths=paths,
    )
    return TradingAgentsRunResult(
        events=tuple(events),
        tool_events=tool_observer.events(),
        artifact=artifact,
        executed_roles=_executed_roles(selected_analysts),
        final_state=final_state,
    )
