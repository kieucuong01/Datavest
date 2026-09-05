"""Native TradingAgents provider configuration and tool provenance callbacks."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any

from langchain_core.callbacks.base import BaseCallbackHandler


_NATIVE_ENV_PREFIXES = ("TRADINGAGENTS_", "DEEPSEEK_")
_ANALYST_TOOL_GROUPS = frozenset({"market", "social", "news", "fundamentals"})


def extract_native_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Return native TradingAgents configuration values unchanged and unlogged."""

    return {
        key: value
        for key, value in environment.items()
        if key.startswith(_NATIVE_ENV_PREFIXES)
    }


def upstream_tool_groups() -> set[str]:
    """Expose the complete upstream tool taxonomy without recreating it."""

    from tradingagents.dataflows.interface import TOOLS_CATEGORIES

    return set(_ANALYST_TOOL_GROUPS | set(TOOLS_CATEGORIES))


def _category_for_tool(tool_name: str) -> str | None:
    from tradingagents.dataflows.interface import get_category_for_method

    try:
        return get_category_for_method(tool_name)
    except ValueError:
        return None


def _vendor_chain(config: Mapping[str, Any], tool_name: str) -> str | None:
    category = _category_for_tool(tool_name)
    if category is None:
        return None
    tool_vendors = config.get("tool_vendors", {})
    if isinstance(tool_vendors, Mapping) and tool_name in tool_vendors:
        return str(tool_vendors[tool_name])
    data_vendors = config.get("data_vendors", {})
    if isinstance(data_vendors, Mapping) and category in data_vendors:
        return str(data_vendors[category])
    return "default"


def _output_text(value: Any) -> str:
    content = getattr(value, "content", value)
    return content if isinstance(content, str) else str(content)


def _result_status(value: str) -> str:
    if value.startswith("NO_DATA_AVAILABLE:") or value.startswith("DATA_UNAVAILABLE:"):
        return "unavailable"
    return "configured"


@dataclass(frozen=True)
class NativeToolEvent:
    tool_name: str
    category: str | None
    vendor_chain: str | None
    status: str
    duration_ms: int
    result_checksum: str


class NativeToolObserver(BaseCallbackHandler):
    """Capture tool provenance without intercepting or replacing upstream tools."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        super().__init__()
        self._config = dict(config)
        self._starts: dict[str, tuple[str, float]] = {}
        self._events: list[NativeToolEvent] = []
        self._lock = Lock()

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        **_: Any,
    ) -> None:
        tool_name = str(serialized.get("name", "unknown"))
        with self._lock:
            self._starts[str(run_id)] = (tool_name, monotonic())

    def on_tool_end(self, output: Any, *, run_id: Any, **_: Any) -> None:
        self._record_completion(str(run_id), _output_text(output), status=None)

    def on_tool_error(self, error: BaseException, *, run_id: Any, **_: Any) -> None:
        self._record_completion(str(run_id), str(error), status="error")

    def _record_completion(self, run_id: str, output: str, status: str | None) -> None:
        with self._lock:
            tool_name, started_at = self._starts.pop(run_id, ("unknown", monotonic()))
            self._events.append(
                NativeToolEvent(
                    tool_name=tool_name,
                    category=_category_for_tool(tool_name),
                    vendor_chain=_vendor_chain(self._config, tool_name),
                    status=status or _result_status(output),
                    duration_ms=max(0, round((monotonic() - started_at) * 1000)),
                    result_checksum=hashlib.sha256(output.encode("utf-8")).hexdigest(),
                )
            )

    def events(self) -> tuple[NativeToolEvent, ...]:
        with self._lock:
            return tuple(self._events)
