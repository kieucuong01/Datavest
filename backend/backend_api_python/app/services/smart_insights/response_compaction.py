"""Compact Smart Insights read models for interactive web clients."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any


EVIDENCE_LIMIT = 8
RECENT_SERIES_POINTS = 365
HISTORICAL_SERIES_POINTS = 120
_GROUP_FIELDS = (
    "metric",
    "symbol",
    "source",
    "component",
    "model",
    "asset",
    "cohort",
    "flowType",
)


def compact_overview_response(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the evidence IDs the workspace can render and expose total counts."""
    result = dict(payload)
    opinions: list[dict[str, Any]] = []
    for raw_opinion in payload.get("opinions", []) or []:
        opinion = dict(raw_opinion)
        evidence = list(opinion.get("evidence", []) or [])
        opinion["evidenceCount"] = len(evidence)
        opinion["evidence"] = evidence[:EVIDENCE_LIMIT]
        opinions.append(opinion)
    result["opinions"] = opinions

    evidence = list(payload.get("evidence", []) or [])
    result["evidenceCount"] = len(evidence)
    result["evidence"] = evidence[:EVIDENCE_LIMIT]
    return result


def compact_pulse_response(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve recent daily history while sampling older chart points."""
    return _compact_value(payload)


def _compact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _compact_series(item) if key == "series" and isinstance(item, list) else _compact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_compact_value(item) for item in value]
    return value


def _compact_series(series: list[Any]) -> list[Any]:
    if len(series) <= RECENT_SERIES_POINTS + HISTORICAL_SERIES_POINTS:
        return [_compact_value(item) for item in series]
    if not all(isinstance(item, Mapping) for item in series):
        return [_compact_value(item) for item in _uniform_sample(series, RECENT_SERIES_POINTS + HISTORICAL_SERIES_POINTS)]

    groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, item in enumerate(series):
        groups[tuple(str(item.get(field) or "") for field in _GROUP_FIELDS)].append(index)

    selected: set[int] = set()
    for indices in groups.values():
        selected.update(_compact_group_indices(series, indices))
    return [_compact_value(series[index]) for index in sorted(selected)]


def _compact_group_indices(series: list[Any], indices: list[int]) -> list[int]:
    limit = RECENT_SERIES_POINTS + HISTORICAL_SERIES_POINTS
    if len(indices) <= limit:
        return indices

    dated = [(index, _point_datetime(series[index])) for index in indices]
    valid_dates = [point_date for _, point_date in dated if point_date is not None]
    if not valid_dates:
        return _uniform_sample(indices, limit)

    cutoff = max(valid_dates) - timedelta(days=RECENT_SERIES_POINTS - 1)
    recent = [index for index, point_date in dated if point_date is not None and point_date >= cutoff]
    historical = [index for index, point_date in dated if point_date is None or point_date < cutoff]
    return [
        *_uniform_sample(historical, HISTORICAL_SERIES_POINTS),
        *_uniform_sample(recent, RECENT_SERIES_POINTS),
    ]


def _uniform_sample(items: list[Any], limit: int) -> list[Any]:
    if len(items) <= limit:
        return list(items)
    if limit <= 1:
        return [items[-1]]
    return [items[round(index * (len(items) - 1) / (limit - 1))] for index in range(limit)]


def _point_datetime(point: Mapping[str, Any]) -> datetime | None:
    raw = point.get("effectiveAt") or point.get("effective_at") or point.get("date") or point.get("observedAt")
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


__all__ = ["compact_overview_response", "compact_pulse_response"]
