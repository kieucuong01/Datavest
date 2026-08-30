"""Import source-backed Smart Insights evidence from the old DataVest schema.

The source connection is read-only. Dry-run is the default; ``--apply`` is
required before the local destination can be changed. The importer moves
evidence and operational provenance, never auth secrets, organizations,
portfolios, broker credentials, or AI keys.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

from app.services.smart_insights.contracts import DataClass, Observation
from app.services.smart_insights.snapshot_pipeline import build_snapshot_draft
from app.services.smart_insights.snapshot_pipeline import METHODOLOGY_VERSION
from app.services.smart_insights.sources import SOURCES


_SUCCESS_STATUSES = {"succeeded", "success", "completed"}
_QUALITY_LIVE = {"passed", "warning"}
_QUALITY_DEMO = {"sample", "demo"}
def _json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return fallback


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _aware(value: Any, *, fallback: datetime | None = None) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return fallback
    return fallback


def _uuid(value: Any) -> str | None:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _dsn_identity(dsn: str) -> tuple[str, int, str]:
    parsed = urlsplit(dsn)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise ValueError("PostgreSQL DSN must include a host")
    return parsed.hostname.lower(), parsed.port or 5432, parsed.path.lstrip("/")


def _safe_source_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    return value


def _run_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return {
        "queued": "QUEUED",
        "running": "RUNNING",
        "succeeded": "SUCCEEDED",
        "success": "SUCCEEDED",
        "completed": "SUCCEEDED",
        "failed": "FAILED",
        "quarantined": "QUARANTINED",
    }.get(normalized, "FAILED")


def _quality_class(raw_status: str, run_status: str, quality_status: str) -> DataClass | None:
    quality = quality_status.strip().lower()
    if quality in _QUALITY_DEMO:
        return DataClass.DEMO
    if raw_status.strip().lower() == "validated" and run_status.strip().lower() in _SUCCESS_STATUSES:
        if quality in _QUALITY_LIVE:
            return DataClass.LIVE
    return None


def _warning_list(value: Any) -> tuple[str, ...]:
    parsed = _json(value, [])
    if isinstance(parsed, list):
        return tuple(str(item)[:200] for item in parsed[:20])
    return ()


def _query(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def _has_table(conn, name: str) -> bool:
    rows = _query(
        conn,
        "SELECT to_regclass(%s) IS NOT NULL AS present",
        (f"public.{name}",),
    )
    return bool(rows and rows[0]["present"])


def _source_definition(code: str):
    return SOURCES.get(code)


def _ensure_destination_source(conn, code: str) -> int | None:
    source = _source_definition(code)
    if source is None:
        return None
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT id FROM data_sources WHERE code = %s", (code,))
        existing = cursor.fetchone()
        if existing:
            return int(existing["id"])
        cursor.execute(
            """
            INSERT INTO data_sources
              (code, name, market, source_url, collection_mode, methodology_version,
               freshness_sla_minutes, enabled, activation_mode, verified_at, metadata_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                source.code,
                source.name,
                source.market,
                source.urls[0],
                source.collection_mode,
                source.methodology_version,
                source.freshness_sla_minutes,
                source.enabled_by_default,
                source.activation_mode,
                source.verified_at,
                json.dumps({"schedule": source.schedule, "activationMode": source.activation_mode}),
            ),
        )
        row = cursor.fetchone()
        return int(row["id"])


def _load_source_data(source_conn) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    providers = _query(
        source_conn,
        "SELECT id, code, name, terms_url, license_scope, status FROM data_providers ORDER BY code",
    )
    runs = _query(
        source_conn,
        """
        SELECT id, provider, status, records_fetched, error_code, retry_count,
               duration_ms, metadata, started_at, finished_at, created_at
        FROM provider_runs
        ORDER BY created_at, id
        """,
    )
    raw = _query(
        source_conn,
        """
        SELECT raw.id, provider.code AS provider_code, raw.source_url,
               raw.effective_at, raw.published_at, raw.observed_at,
               raw.content_hash, raw.content_type, raw.storage_locator,
               raw.parser_version, raw.status, raw.error_code, raw.metadata
        FROM insight_raw_snapshots raw
        JOIN data_providers provider ON provider.id = raw.provider_id
        ORDER BY raw.observed_at, raw.id
        """,
    )
    metrics = _query(
        source_conn,
        """
        SELECT observation.id, observation.metric_definition_id,
               observation.provider_id, observation.raw_snapshot_id,
               observation.effective_at, observation.effective_start,
               observation.effective_end, observation.published_at,
               observation.observed_at, observation.revision, observation.value,
               observation.natural_key, observation.dimension_key,
               observation.dimensions, observation.quality_status,
               observation.quality_flags, metric.code AS metric_code,
               metric.market, metric.unit, metric.methodology_version,
               provider.code AS provider_code, asset.symbol AS asset_symbol,
               raw.source_url, raw.status AS raw_status,
               raw.observed_at AS raw_observed_at
        FROM metric_observations observation
        JOIN metric_definitions metric ON metric.id = observation.metric_definition_id
        JOIN data_providers provider ON provider.id = observation.provider_id
        JOIN insight_raw_snapshots raw ON raw.id = observation.raw_snapshot_id
        LEFT JOIN assets asset ON asset.id = observation.asset_id
        ORDER BY observation.observed_at, observation.id
        """,
    )
    return providers, runs, {str(row["id"]): row for row in raw}, metrics


def _nearest_run(
    provider_code: str,
    observed_at: datetime,
    runs_by_provider: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    candidates = runs_by_provider.get(provider_code, [])
    if not candidates:
        return None
    nearest = min(
        candidates,
        key=lambda row: abs((_aware(row.get("created_at"), fallback=observed_at) - observed_at).total_seconds()),
    )
    created_at = _aware(nearest.get("created_at"), fallback=observed_at)
    if created_at is None or abs((created_at - observed_at).total_seconds()) > timedelta(days=8).total_seconds():
        return None
    return nearest


def _metric_observation(row: dict[str, Any], raw: dict[str, Any], run: dict[str, Any] | None) -> Observation | None:
    data_class = _quality_class(
        str(raw.get("status") or row.get("raw_status") or ""),
        str((run or {}).get("status") or ""),
        str(row.get("quality_status") or ""),
    )
    if data_class is None:
        return None
    source_url = _safe_source_url(row.get("source_url") or raw.get("source_url"))
    effective_at = _aware(row.get("effective_at"))
    observed_at = _aware(row.get("observed_at"), fallback=_aware(raw.get("observed_at")))
    if source_url is None or effective_at is None or observed_at is None:
        return None
    value = {
        "metric": str(row["metric_code"]),
        "value": str(row["value"]),
        "unit": str(row.get("unit") or ""),
        "dimensions": _json(row.get("dimensions"), {}),
        "qualityStatus": str(row.get("quality_status") or ""),
        "qualityFlags": list(_warning_list(row.get("quality_flags"))),
        "naturalKey": str(row.get("natural_key") or ""),
        "revision": int(row.get("revision") or 1),
        "legacyObservationId": str(row["id"]),
        "legacyRawSnapshotId": str(row["raw_snapshot_id"]),
    }
    warnings = _warning_list(row.get("quality_flags"))
    return Observation.create(
        source_code=str(row["provider_code"]),
        source_url=source_url,
        market=str(row["market"]).lower(),
        effective_at=effective_at,
        published_at=_aware(row.get("published_at")),
        observed_at=observed_at,
        methodology_version=str(row.get("methodology_version") or "legacy-import-v1"),
        value=value,
        warnings=warnings,
        data_class=data_class,
        symbol=str(row["asset_symbol"]).upper() if row.get("asset_symbol") else None,
    )


def _event_observation(row: dict[str, Any], raw: dict[str, Any], run: dict[str, Any] | None) -> Observation | None:
    quality_status = str(row.get("quality_status") or "")
    data_class = _quality_class(
        str(raw.get("status") or ""),
        str((run or {}).get("status") or ""),
        quality_status,
    )
    if data_class is None:
        return None
    source_url = _safe_source_url(raw.get("source_url") or row.get("detail_url"))
    observed_at = _aware(row.get("observed_at"), fallback=_aware(raw.get("observed_at")))
    effective_at = _aware(row.get("event_at"), fallback=_aware(row.get("event_date")))
    if source_url is None or observed_at is None or effective_at is None:
        return None
    value = {
        "metric": "macro.economic_event",
        "event": str(row.get("event") or ""),
        "country": str(row.get("country") or ""),
        "currency": str(row.get("currency") or ""),
        "impact": str(row.get("impact") or ""),
        "actual": row.get("actual"),
        "forecast": row.get("forecast"),
        "previous": row.get("previous"),
        "timeStatus": str(row.get("time_status") or ""),
        "sourceEventKey": str(row.get("source_event_key") or ""),
        "revision": int(row.get("revision") or 1),
        "legacyEventId": str(row["id"]),
    }
    return Observation.create(
        source_code=str(row["source_code"]),
        source_url=source_url,
        market="macro",
        effective_at=effective_at,
        published_at=_aware(row.get("published_at")),
        observed_at=observed_at,
        methodology_version="legacy-event-import-v1",
        value=value,
        warnings=_warning_list(row.get("quality_flags")),
        data_class=data_class,
    )


def _insert_run(conn, row: dict[str, Any], source_id: int, market: str) -> str | None:
    run_id = _uuid(row.get("id"))
    if run_id is None:
        return None
    status = _run_status(row.get("status"))
    request_json = {
        "legacyProvider": str(row.get("provider") or ""),
        "legacyProviderRunId": run_id,
        "legacyMetadata": _json(row.get("metadata"), {}),
    }
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            INSERT INTO collector_runs
              (id, data_source_id, market, status, started_at, finished_at,
               records_fetched, records_persisted, error_code, warnings_json, request_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, '[]'::jsonb, %s::jsonb)
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            """,
            (
                run_id,
                source_id,
                market,
                status,
                _aware(row.get("started_at")),
                _aware(row.get("finished_at")),
                int(row.get("records_fetched") or 0),
                str(row.get("error_code")) if row.get("error_code") else None,
                json.dumps(request_json, ensure_ascii=False, default=str),
            ),
        )
        inserted = cursor.fetchone()
        return run_id if inserted or status else run_id


def _load_destination_source_ids(conn, codes: Iterable[str]) -> dict[str, int]:
    wanted = tuple(sorted(set(codes)))
    if not wanted:
        return {}
    rows = _query(
        conn,
        "SELECT id, code FROM data_sources WHERE code = ANY(%s)",
        (list(wanted),),
    )
    return {str(row["code"]): int(row["id"]) for row in rows}


def _destination_has_checksum(conn, source_id: int | None, checksum: str) -> bool:
    if source_id is None:
        return False
    rows = _query(
        conn,
        "SELECT 1 AS present FROM observations WHERE data_source_id = %s AND checksum = %s",
        (source_id, checksum),
    )
    return bool(rows)


def _insert_observation(
    conn,
    observation: Observation,
    source_id: int,
    collector_run_id: str | None,
) -> tuple[str, bool]:
    observation_id = str(uuid4())
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            INSERT INTO observations
              (id, data_source_id, collector_run_id, market, symbol, effective_at,
               published_at, observed_at, source_url, methodology_version,
               value_json, warnings_json, checksum, data_class)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
            ON CONFLICT (data_source_id, checksum) DO NOTHING
            RETURNING id
            """,
            (
                observation_id,
                source_id,
                collector_run_id,
                observation.market,
                observation.symbol,
                observation.effective_at,
                observation.published_at,
                observation.observed_at,
                observation.source_url,
                observation.methodology_version,
                json.dumps(observation.value, ensure_ascii=False, default=str),
                json.dumps(list(observation.warnings), ensure_ascii=False),
                observation.checksum,
                observation.data_class.value,
            ),
        )
        row = cursor.fetchone()
        if row:
            return str(row["id"]), True
        cursor.execute(
            "SELECT id FROM observations WHERE data_source_id = %s AND checksum = %s",
            (source_id, observation.checksum),
        )
        existing = cursor.fetchone()
        if not existing:
            raise RuntimeError("observation_dedupe_lookup_failed")
        return str(existing["id"]), False


def _materialize(conn, observation_ids: Iterable[str], *, window_days: int) -> int:
    ids = list(dict.fromkeys(str(item) for item in observation_ids))
    if not ids:
        return 0
    rows = _query(
        conn,
        """
        SELECT o.id, o.market, o.symbol, o.effective_at, o.published_at,
               o.observed_at, o.source_url, o.methodology_version,
               o.value_json, o.warnings_json, o.checksum, o.data_class,
               source.code AS source_code
        FROM observations o
        JOIN data_sources source ON source.id = o.data_source_id
        WHERE o.id = ANY(%s)
        ORDER BY o.market, o.data_class, o.observed_at, o.id
        """,
        (ids,),
    )
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["market"]).lower(), str(row["data_class"]).upper())].append(row)
    created = 0
    for (market, data_class), group in grouped.items():
        latest = max(_aware(row["observed_at"]) for row in group)
        cutoff = latest - timedelta(days=max(0, window_days))
        selected = [row for row in group if _aware(row["observed_at"]) >= cutoff]
        evidence = [
            {
                "id": str(row["id"]),
                "market": row["market"],
                "symbol": row["symbol"],
                "source": row["source_code"],
                "sourceUrl": row["source_url"],
                "effectiveAt": _iso(row["effective_at"]),
                "publishedAt": _iso(row["published_at"]),
                "observedAt": _iso(row["observed_at"]),
                "methodologyVersion": row["methodology_version"],
                "warnings": _json(row["warnings_json"], []),
                "checksum": row["checksum"],
                "dataClass": data_class,
                "value": _json(row["value_json"], {}),
            }
            for row in selected
        ]
        if not evidence:
            continue
        draft = build_snapshot_draft(
            evidence,
            market=market,
            mode=data_class.lower(),
            as_of=max(_aware(row["observed_at"]) for row in selected),
        )
        snapshot_id = str(uuid4())
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                INSERT INTO insight_snapshots
                  (id, as_of, market, status, methodology_version, summary_json,
                   evidence_checksum, data_class)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (market, as_of, methodology_version, data_class, evidence_checksum)
                DO NOTHING
                RETURNING id
                """,
                (
                    snapshot_id,
                    draft.as_of,
                    draft.market,
                    draft.status,
                    METHODOLOGY_VERSION,
                    json.dumps(draft.summary, ensure_ascii=False, default=str),
                    draft.evidence_checksum,
                    draft.data_class,
                ),
            )
            inserted = cursor.fetchone()
            if not inserted:
                continue
            created += 1
            for opinion in draft.opinions:
                opinion_id = str(uuid4())
                cursor.execute(
                    """
                    INSERT INTO asset_opinions
                      (id, insight_snapshot_id, market, symbol, stance, score, confidence,
                       rationale_json, explanation, explanation_model, evidence_validated, data_class)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                    """,
                    (
                        opinion_id,
                        snapshot_id,
                        opinion.market,
                        opinion.symbol,
                        opinion.stance,
                        opinion.score,
                        opinion.confidence,
                        json.dumps(opinion.rationale, ensure_ascii=False, default=str),
                        opinion.explanation,
                        opinion.explanation_model,
                        opinion.evidence_validated,
                        opinion.data_class,
                    ),
                )
                for evidence_id in opinion.evidence_ids:
                    cursor.execute(
                        """
                        INSERT INTO insight_evidence_links
                          (insight_snapshot_id, asset_opinion_id, observation_id, evidence_role)
                        VALUES (%s, %s, %s, 'SUPPORTING')
                        ON CONFLICT DO NOTHING
                        """,
                        (snapshot_id, opinion_id, evidence_id),
                    )
            opinion_evidence = {item for opinion in draft.opinions for item in opinion.evidence_ids}
            for evidence_id in draft.evidence_ids:
                if evidence_id in opinion_evidence:
                    continue
                cursor.execute(
                    """
                    INSERT INTO insight_evidence_links
                      (insight_snapshot_id, asset_opinion_id, observation_id, evidence_role)
                    VALUES (%s, NULL, %s, 'CONTEXT')
                    ON CONFLICT DO NOTHING
                    """,
                    (snapshot_id, evidence_id),
                )
    return created


def migrate(
    *,
    source_dsn: str,
    target_dsn: str,
    apply: bool,
    limit: int = 0,
    materialize_days: int = 30,
) -> dict[str, Any]:
    if apply and _dsn_identity(source_dsn) == _dsn_identity(target_dsn):
        raise ValueError("source and target databases must differ")
    report: dict[str, Any] = {
        "mode": "APPLY" if apply else "DRY_RUN",
        "status": "OK",
        "sourcesSeen": 0,
        "sourcesKnown": 0,
        "runsSeen": 0,
        "runsImported": 0,
        "metricRowsSeen": 0,
        "eventRowsSeen": 0,
        "observationsInserted": 0,
        "observationsEligible": 0,
        "observationsDeduped": 0,
        "observationsSkipped": 0,
        "snapshotsCreated": 0,
        "skippedReasons": Counter(),
        "warnings": [],
    }
    with closing(psycopg2.connect(source_dsn)) as source_conn:
        source_conn.set_session(readonly=True, autocommit=False)
        with closing(psycopg2.connect(target_dsn)) as target_conn:
            target_conn.set_session(readonly=not apply, autocommit=False)
            providers, runs, raw_by_id, metrics = _load_source_data(source_conn)
            report["sourcesSeen"] = len(providers)
            known_codes = {str(row["code"]) for row in providers if _source_definition(str(row["code"]))}
            report["sourcesKnown"] = len(known_codes)
            report["runsSeen"] = len(runs)
            if limit > 0:
                metrics = metrics[:limit]
            report["metricRowsSeen"] = len(metrics)
            runs_by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
            run_ids_by_legacy_id: dict[str, str] = {}
            destination_source_ids: dict[str, int] = {}
            if apply:
                for code in sorted(known_codes):
                    source_id = _ensure_destination_source(target_conn, code)
                    if source_id is not None:
                        destination_source_ids[code] = source_id
                for run in runs:
                    code = str(run.get("provider") or "")
                    source_id = destination_source_ids.get(code)
                    if source_id is None:
                        continue
                    source = _source_definition(code)
                    run_id = _insert_run(target_conn, run, source_id, source.market)
                    if run_id:
                        report["runsImported"] += 1
                        run_ids_by_legacy_id[str(run["id"])] = run_id
                    runs_by_provider[code].append(run)
            else:
                destination_source_ids = _load_destination_source_ids(target_conn, known_codes)
                for run in runs:
                    if str(run.get("provider") or "") in known_codes:
                        runs_by_provider[str(run["provider"])].append(run)
            imported_ids: list[str] = []
            persisted_by_run: Counter[str] = Counter()
            for row in metrics:
                code = str(row["provider_code"])
                raw = raw_by_id.get(str(row["raw_snapshot_id"]))
                if raw is None:
                    report["observationsSkipped"] += 1
                    report["skippedReasons"]["missing_raw_snapshot"] += 1
                    continue
                observed = _aware(row.get("observed_at"), fallback=_aware(raw.get("observed_at")))
                run = _nearest_run(code, observed or datetime.now(timezone.utc), runs_by_provider)
                try:
                    observation = _metric_observation(row, raw, run)
                except (TypeError, ValueError):
                    observation = None
                if observation is None:
                    report["observationsSkipped"] += 1
                    report["skippedReasons"]["evidence_policy_or_provenance"] += 1
                    continue
                if not apply:
                    report["observationsEligible"] += 1
                    if _destination_has_checksum(
                        target_conn, destination_source_ids.get(code), observation.checksum
                    ):
                        report["observationsDeduped"] += 1
                    continue
                source_id = destination_source_ids.get(code)
                if source_id is None:
                    report["observationsSkipped"] += 1
                    report["skippedReasons"]["unknown_source"] += 1
                    continue
                run_id = run_ids_by_legacy_id.get(str(run.get("id"))) if run else None
                observation_id, created = _insert_observation(target_conn, observation, source_id, run_id)
                imported_ids.append(observation_id)
                report["observationsInserted"] += int(created)
                report["observationsDeduped"] += int(not created)
                if run_id and created:
                    persisted_by_run[run_id] += 1
            if _has_table(source_conn, "economic_events"):
                events = _query(
                    source_conn,
                    """
                    SELECT id, source_code, source_event_key, event, country, currency,
                           impact, actual, forecast, previous, event_date, event_at,
                           time_status, detail_url, raw_snapshot_id, published_at,
                           observed_at, revision, quality_status, quality_flags
                    FROM economic_events
                    ORDER BY observed_at, id
                    """,
                )
                report["eventRowsSeen"] = len(events)
                for row in events[:limit or None]:
                    code = str(row["source_code"])
                    raw = raw_by_id.get(str(row.get("raw_snapshot_id")))
                    if raw is None or code not in destination_source_ids:
                        report["observationsSkipped"] += 1
                        report["skippedReasons"]["event_missing_raw_or_source"] += 1
                        continue
                    observed = _aware(row.get("observed_at"), fallback=_aware(raw.get("observed_at")))
                    run = _nearest_run(code, observed or datetime.now(timezone.utc), runs_by_provider)
                    try:
                        observation = _event_observation(row, raw, run)
                    except (TypeError, ValueError):
                        observation = None
                    if observation is None:
                        report["observationsSkipped"] += 1
                        report["skippedReasons"]["event_evidence_policy_or_provenance"] += 1
                        continue
                    if not apply:
                        report["observationsEligible"] += 1
                        if _destination_has_checksum(
                            target_conn, destination_source_ids.get(code), observation.checksum
                        ):
                            report["observationsDeduped"] += 1
                        continue
                    source_id = destination_source_ids[code]
                    run_id = run_ids_by_legacy_id.get(str(run.get("id"))) if run else None
                    observation_id, created = _insert_observation(target_conn, observation, source_id, run_id)
                    imported_ids.append(observation_id)
                    report["observationsInserted"] += int(created)
                    report["observationsDeduped"] += int(not created)
            if apply:
                for run_id, count in persisted_by_run.items():
                    with target_conn.cursor() as cursor:
                        cursor.execute(
                            "UPDATE collector_runs SET records_persisted = GREATEST(records_persisted, %s) WHERE id = %s",
                            (count, run_id),
                        )
                report["snapshotsCreated"] = _materialize(
                    target_conn, imported_ids, window_days=materialize_days
                )
                target_conn.commit()
            else:
                target_conn.rollback()
            report["skippedReasons"] = dict(report["skippedReasons"])
            report["warningCount"] = len(report["warnings"])
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn", default=None, help="Source PostgreSQL DSN; prefer SOURCE_DATABASE_URL")
    parser.add_argument("--target-dsn", default=None, help="Destination PostgreSQL DSN; prefer DATABASE_URL")
    parser.add_argument("--apply", action="store_true", help="Write to the destination; dry-run is the default")
    parser.add_argument("--limit", type=int, default=0, help="Maximum metric/event rows to inspect; 0 means all")
    parser.add_argument("--materialize-days", type=int, default=30)
    parser.add_argument("--report", type=Path, default=None, help="Write the redacted JSON report to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_dsn = args.source_dsn or os.getenv("SOURCE_DATABASE_URL", "").strip()
    target_dsn = args.target_dsn or os.getenv("DATABASE_URL", "").strip()
    if not source_dsn or not target_dsn:
        raise SystemExit("SOURCE_DATABASE_URL and DATABASE_URL are required")
    report = migrate(
        source_dsn=source_dsn,
        target_dsn=target_dsn,
        apply=args.apply,
        limit=max(0, args.limit),
        materialize_days=max(0, args.materialize_days),
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
