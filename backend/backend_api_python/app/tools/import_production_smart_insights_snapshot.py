"""Import a browser-exported DataVest production Smart Insights snapshot.

The payload is deliberately evidence-only: it contains no credentials, account
records, portfolio positions, broker data, or provider secrets.  Input is
expected on stdin so a one-time local Docker job can receive it without writing
an intermediate export to disk.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.services.smart_insights.contracts import DataClass, Observation
from app.services.smart_insights.repository import SmartInsightsRepository
from app.services.smart_insights.snapshot_pipeline import SnapshotMaterializer
from app.services.smart_insights.sources import SOURCES


SNAPSHOT_VERSION = "datavest-production-smart-insights-v1"
_SOURCE_ALIASES = {"deribit-public": "openbb-deribit"}
_MARKETS = frozenset({"crypto", "macro", "vn", "us", "gold"})
_MAX_METRICS = 10_000
_MAX_EVENTS = 1_000


class SnapshotImportError(ValueError):
    """Raised when an untrusted snapshot cannot satisfy the evidence contract."""


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise SnapshotImportError(f"invalid_{field}")
    return value


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotImportError(f"missing_{field}")
    try:
        normalized = value.strip()
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotImportError(f"invalid_{field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if len(normalized) == 10:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            raise SnapshotImportError(f"invalid_{field}")
    return parsed.astimezone(timezone.utc)


def _source_code(value: object) -> str:
    code = _SOURCE_ALIASES.get(str(value or "").strip().lower(), str(value or "").strip().lower())
    if code not in SOURCES:
        raise SnapshotImportError("unknown_source")
    return code


def _warnings(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or len(value) > 50:
        raise SnapshotImportError("invalid_warnings")
    return tuple(str(item)[:200] for item in value)


def production_metric_observation(row: Mapping[str, object]) -> Observation:
    source_code = _source_code(row.get("sourceCode"))
    market = str(row.get("market") or "").strip().lower()
    if market not in _MARKETS:
        raise SnapshotImportError("invalid_market")
    metric = str(row.get("metricCode") or "").strip()
    source_url = str(row.get("sourceUrl") or "").strip()
    if not metric or not source_url:
        raise SnapshotImportError("missing_metric_provenance")
    effective_at = _timestamp(
        row.get("effectiveEnd") or row.get("effectiveStart") or row.get("observedAt"),
        field="effective_at",
    )
    observed_at = _timestamp(row.get("observedAt"), field="observed_at")
    try:
        return Observation.create(
            source_code=source_code,
            source_url=source_url,
            market=market,
            symbol=str(row["asset"]).strip().upper() if row.get("asset") else None,
            effective_at=effective_at,
            observed_at=observed_at,
            methodology_version=str(row.get("methodologyVersion") or "datavest-production-v1"),
            value={
                "metric": metric,
                "value": row.get("value"),
                "unit": str(row.get("unit") or ""),
                "delta": row.get("delta"),
                "percentile": row.get("percentile"),
                "freshness": row.get("freshness"),
                "legacyObservationId": str(row.get("observationId") or "") or None,
            },
            warnings=_warnings(row.get("qualityWarnings")),
            data_class=DataClass.LIVE,
        )
    except ValueError as exc:
        raise SnapshotImportError("invalid_observation") from exc


def production_calendar_observation(row: Mapping[str, object]) -> Observation:
    source_code = _source_code(row.get("sourceCode"))
    source_url = str(row.get("sourceUrl") or "").strip()
    event = str(row.get("event") or "").strip()
    if not source_url or not event:
        raise SnapshotImportError("missing_event_provenance")
    effective_at = _timestamp(row.get("eventAt") or row.get("eventDate"), field="event_at")
    observed_at = _timestamp(row.get("observedAt") or row.get("eventAt"), field="observed_at")
    try:
        return Observation.create(
            source_code=source_code,
            source_url=source_url,
            market="macro",
            effective_at=effective_at,
            observed_at=observed_at,
            methodology_version="datavest-production-calendar-v1",
            value={
                "metric": "macro.economic_event",
                "event": event,
                "country": str(row.get("country") or ""),
                "currency": str(row.get("currency") or ""),
                "impact": str(row.get("impact") or ""),
                "actual": row.get("actual"),
                "forecast": row.get("forecast"),
                "previous": row.get("previous"),
                "timeStatus": str(row.get("timeStatus") or ""),
                "legacyEventId": str(row.get("id") or "") or None,
            },
            warnings=(),
            data_class=DataClass.LIVE,
        )
    except ValueError as exc:
        raise SnapshotImportError("invalid_observation") from exc


def parse_snapshot(payload: object) -> list[Observation]:
    body = _mapping(payload, field="snapshot")
    if body.get("version") != SNAPSHOT_VERSION:
        raise SnapshotImportError("unsupported_snapshot_version")
    metrics = body.get("metrics")
    events = body.get("events")
    if not isinstance(metrics, list) or not isinstance(events, list):
        raise SnapshotImportError("invalid_snapshot_payload")
    if len(metrics) > _MAX_METRICS or len(events) > _MAX_EVENTS:
        raise SnapshotImportError("snapshot_too_large")
    return [
        *(production_metric_observation(_mapping(row, field="metric")) for row in metrics),
        *(production_calendar_observation(_mapping(row, field="event")) for row in events),
    ]


def import_snapshot(payload: object, *, apply: bool) -> dict[str, Any]:
    observations = parse_snapshot(payload)
    report: dict[str, Any] = {
        "version": SNAPSHOT_VERSION,
        "mode": "APPLY" if apply else "DRY_RUN",
        "observationsReceived": len(observations),
        "observationsInserted": 0,
        "observationsDeduped": 0,
        "snapshots": [],
    }
    if not apply:
        report["sources"] = sorted({observation.source_code for observation in observations})
        return report

    repository = SmartInsightsRepository()
    source_ids: dict[str, int] = {}
    persisted: list[tuple[str, Observation]] = []
    for observation in observations:
        source_id = source_ids.get(observation.source_code)
        if source_id is None:
            source_id = repository.resolve_data_source(observation.source_code)
            source_ids[observation.source_code] = source_id
        identifier, created = repository.upsert_observation(
            observation,
            data_source_id=source_id,
            collector_run_id=None,
        )
        persisted.append((identifier, observation))
        report["observationsInserted"] += int(created)
        report["observationsDeduped"] += int(not created)
    report["snapshots"] = SnapshotMaterializer(repository=repository).publish_observations(persisted)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdin", action="store_true", help="Read the JSON snapshot from stdin")
    parser.add_argument("--apply", action="store_true", help="Write evidence to the local destination")
    args = parser.parse_args(argv)
    if not args.stdin:
        raise SystemExit("--stdin is required")
    try:
        payload = json.load(sys.stdin)
        report = import_snapshot(payload, apply=args.apply)
    except (json.JSONDecodeError, SnapshotImportError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}))
        return 2
    print(json.dumps({"status": "OK", **report}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
