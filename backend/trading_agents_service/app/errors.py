"""Failure classification owned by the service integration boundary."""

from __future__ import annotations


def failure_code(error: BaseException) -> str:
    """Classify provider timeouts without importing a possibly stale vendor helper."""

    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, TimeoutError) or "timeout" in type(current).__name__.lower():
            return "provider_timeout"
        current = current.__cause__ or current.__context__
    return "runner_failed"


__all__ = ["failure_code"]
