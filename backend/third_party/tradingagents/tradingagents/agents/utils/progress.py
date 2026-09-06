"""Optional, non-content progress hooks for long-running native agents.

The hook is intentionally context-local. The upstream graph keeps ownership of
the execution flow; a host such as DataVest can observe safe lifecycle markers
without receiving prompts, model output, or credentials.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any


ProgressSink = Callable[[Mapping[str, Any]], None]
_sink: ContextVar[ProgressSink | None] = ContextVar("tradingagents_progress_sink", default=None)


@contextmanager
def bind_progress_sink(sink: ProgressSink | None) -> Iterator[None]:
    """Bind a best-effort observer to the current native graph execution."""

    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)


def emit_progress(payload: Mapping[str, Any]) -> None:
    """Publish one safe progress marker and never affect the native graph."""

    sink = _sink.get()
    if sink is None:
        return
    try:
        sink(dict(payload))
    except Exception:
        # Progress is observability only. A host callback must never change
        # TradingAgents' analysis behavior.
        return


__all__ = ["ProgressSink", "bind_progress_sink", "emit_progress"]
