"""PostgreSQL persistence for Smart Insights provenance and read models."""

from __future__ import annotations

import json
import hashlib
from datetime import date
from typing import Any, Mapping
from uuid import uuid4

from app.services.smart_insights.contracts import Observation
from app.services.smart_insights.health import classify_freshness
from app.utils.db import get_db_connection


def _json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback
    return value


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


class SmartInsightsRepository:
    def get_production_account_import(
        self, *, user_id: int, data_type: str
    ) -> dict[str, Any] | None:
        """Load only the latest raw import record owned by the requesting user."""
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT payload, payload_checksum, source_updated_at
                FROM qd_production_account_imports
                WHERE user_id = ? AND data_type = ?
                ORDER BY imported_at DESC, id DESC
                LIMIT 1
                """,
                (int(user_id), str(data_type)),
            )
            row = cur.fetchone()
            cur.close()
        if not row:
            return None
        return {
            "payload": _json_value(row["payload"], {}),
            "checksum": str(row["payload_checksum"] or ""),
            "sourceUpdatedAt": _iso(row["source_updated_at"]),
        }

    def list_pulse_observations(
        self, *, data_class: str, as_of: str | None
    ) -> list[dict[str, Any]]:
        """Return bounded, provenance-complete evidence for the pulse read model."""
        params: list[Any] = [data_class]
        as_of_filter = ""
        if as_of:
            as_of_filter = "AND o.effective_at < (?::date + INTERVAL '1 day')"
            params.append(as_of)
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                f"""
                SELECT o.id, o.market, o.symbol, o.effective_at, o.published_at,
                       o.observed_at, o.source_url, o.methodology_version,
                       o.value_json, o.warnings_json, o.checksum, o.data_class,
                       s.code AS source_code
                FROM observations o
                JOIN data_sources s ON s.id = o.data_source_id
                WHERE o.data_class = ?
                  AND o.effective_at >= NOW() - INTERVAL '730 days'
                  {as_of_filter}
                  AND (o.market = 'crypto' OR s.code = 'cryptocraft')
                ORDER BY o.effective_at ASC, o.observed_at ASC, o.id ASC
                LIMIT 20000
                """,
                tuple(params),
            )
            rows = cur.fetchall() or []
            cur.close()
        return [self._evidence_row(row) for row in rows]

    def load_snapshot_evidence(self, run_id: str) -> list[dict[str, Any]]:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT o.id, o.market, o.symbol, o.effective_at, o.published_at,
                       o.observed_at, o.source_url, o.methodology_version,
                       o.value_json, o.warnings_json, o.checksum, o.data_class,
                       s.code AS source_code
                FROM observations o
                JOIN data_sources s ON s.id = o.data_source_id
                WHERE o.collector_run_id = ?
                ORDER BY o.checksum, o.id
                """,
                (run_id,),
            )
            rows = cur.fetchall() or []
            cur.close()
        return [self._evidence_row(row) for row in rows]

    @staticmethod
    def _evidence_row(row: Mapping[str, Any]) -> dict[str, Any]:
        warnings = _json_value(row["warnings_json"], [])
        if str(row["data_class"] or "").upper() != "LIVE" or not row["source_url"] or not row["checksum"]:
            reliability = "LOW"
        elif warnings:
            reliability = "MEDIUM"
        else:
            reliability = "HIGH"
        return {
            "id": str(row["id"]),
            "market": row["market"],
            "symbol": row["symbol"],
            "source": row["source_code"],
            "sourceUrl": row["source_url"],
            "effectiveAt": _iso(row["effective_at"]),
            "publishedAt": _iso(row["published_at"]),
            "observedAt": _iso(row["observed_at"]),
            "methodologyVersion": row["methodology_version"],
            "warnings": warnings,
            "checksum": row["checksum"],
            "dataClass": row["data_class"],
            "reliability": reliability,
            "value": _json_value(row["value_json"], {}),
        }

    def publish_snapshot(self, draft) -> tuple[str, bool]:
        snapshot_id = str(uuid4())
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO insight_snapshots
                    (id, as_of, market, status, methodology_version, summary_json,
                     evidence_checksum, data_class)
                VALUES (?, ?, ?, ?, ?, ?::jsonb, ?, ?)
                ON CONFLICT (market, as_of, methodology_version, data_class, evidence_checksum)
                DO NOTHING
                RETURNING id
                """,
                (
                    snapshot_id,
                    draft.as_of,
                    draft.market,
                    draft.status,
                    draft.methodology_version,
                    json.dumps(draft.summary, ensure_ascii=False, default=str),
                    draft.evidence_checksum,
                    draft.data_class,
                ),
            )
            inserted = cur.fetchone()
            if not inserted:
                cur.execute(
                    """
                    SELECT id FROM insight_snapshots
                    WHERE market = ? AND as_of = ? AND methodology_version = ?
                      AND data_class = ? AND evidence_checksum = ?
                    """,
                    (
                        draft.market,
                        draft.as_of,
                        draft.methodology_version,
                        draft.data_class,
                        draft.evidence_checksum,
                    ),
                )
                existing = cur.fetchone()
                if not existing:
                    raise RuntimeError("snapshot_dedupe_lookup_failed")
                db.commit()
                cur.close()
                return str(existing["id"]), False
            snapshot_id = str(inserted["id"])
            opinion_evidence: set[str] = set()
            for opinion in draft.opinions:
                opinion_id = str(uuid4())
                cur.execute(
                    """
                    INSERT INTO asset_opinions
                        (id, insight_snapshot_id, market, symbol, stance, score,
                         confidence, rationale_json, explanation, explanation_model,
                         evidence_validated, data_class)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?, ?, ?, ?)
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
                    opinion_evidence.add(evidence_id)
                    cur.execute(
                        """
                        INSERT INTO insight_evidence_links
                            (insight_snapshot_id, asset_opinion_id, observation_id, evidence_role)
                        VALUES (?, ?, ?, 'SUPPORTING')
                        """,
                        (snapshot_id, opinion_id, evidence_id),
                    )
            for evidence_id in draft.evidence_ids:
                if evidence_id in opinion_evidence:
                    continue
                cur.execute(
                    """
                    INSERT INTO insight_evidence_links
                        (insight_snapshot_id, asset_opinion_id, observation_id, evidence_role)
                    VALUES (?, NULL, ?, 'CONTEXT')
                    """,
                    (snapshot_id, evidence_id),
                )
            db.commit()
            cur.close()
        return snapshot_id, True

    def load_refresh_request(self, run_id: str) -> dict[str, Any]:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                "SELECT id, market, status, request_json FROM collector_runs WHERE id = ?",
                (run_id,),
            )
            row = cur.fetchone()
            cur.close()
        if not row:
            raise ValueError("refresh_run_not_found")
        request_json = _json_value(row["request_json"], {})
        return {
            "id": str(row["id"]),
            "market": row["market"],
            "status": row["status"],
            "sourceCodes": tuple(request_json.get("sourceCodes") or ()),
        }

    def mark_run_running(self, run_id: str) -> None:
        self._update_run(run_id, status="RUNNING")

    def mark_run_succeeded(
        self,
        run_id: str,
        *,
        records_fetched: int,
        records_persisted: int,
        warnings: tuple[str, ...],
    ) -> None:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                UPDATE collector_runs
                SET status = 'SUCCEEDED', finished_at = NOW(), records_fetched = ?,
                    records_persisted = ?, warnings_json = ?::jsonb, error_code = NULL
                WHERE id = ?
                """,
                (records_fetched, records_persisted, json.dumps(warnings), run_id),
            )
            if cur.rowcount != 1:
                raise ValueError("refresh_run_not_found")
            db.commit()
            cur.close()

    def mark_run_partial(
        self,
        run_id: str,
        *,
        records_fetched: int,
        records_persisted: int,
        warnings: tuple[str, ...],
    ) -> None:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                UPDATE collector_runs
                SET status = 'PARTIAL', finished_at = NOW(), records_fetched = ?,
                    records_persisted = ?, warnings_json = ?::jsonb,
                    error_code = 'SOURCE_PARTIAL'
                WHERE id = ?
                """,
                (records_fetched, records_persisted, json.dumps(warnings), run_id),
            )
            if cur.rowcount != 1:
                raise ValueError("refresh_run_not_found")
            db.commit()
            cur.close()

    def mark_run_failed(
        self, run_id: str, *, error_code: str, warnings: tuple[str, ...]
    ) -> None:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                UPDATE collector_runs
                SET status = 'FAILED', finished_at = NOW(), error_code = ?,
                    warnings_json = ?::jsonb
                WHERE id = ?
                """,
                (error_code, json.dumps(warnings), run_id),
            )
            db.commit()
            cur.close()

    def _update_run(self, run_id: str, *, status: str) -> None:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                UPDATE collector_runs
                SET status = ?, started_at = CASE WHEN ? = 'RUNNING' THEN NOW() ELSE started_at END
                WHERE id = ? AND status = 'QUEUED'
                """,
                (status, status, run_id),
            )
            if cur.rowcount != 1:
                raise ValueError("refresh_run_not_queued")
            db.commit()
            cur.close()

    def resolve_data_source(self, code: str) -> int:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("SELECT id FROM data_sources WHERE code = ? AND enabled = TRUE", (code,))
            row = cur.fetchone()
            cur.close()
        if not row:
            raise ValueError("data_source_unavailable")
        return int(row["id"])

    def create_refresh_request(
        self,
        *,
        requested_by_user_id: int | None,
        market: str | None,
        source_codes: tuple[str, ...],
    ) -> str:
        run_id = str(uuid4())
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO collector_runs
                    (id, requested_by_user_id, market, status, request_json)
                VALUES (?, ?, ?, 'QUEUED', ?::jsonb)
                """,
                (run_id, requested_by_user_id, market, json.dumps({"sourceCodes": source_codes})),
            )
            db.commit()
            cur.close()
        return run_id

    def list_enabled_source_codes(self) -> tuple[str, ...]:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("SELECT code FROM data_sources WHERE enabled = TRUE ORDER BY code")
            rows = cur.fetchall() or []
            cur.close()
        return tuple(str(row["code"]) for row in rows)

    def upsert_observation(
        self,
        observation: Observation,
        *,
        data_source_id: int,
        collector_run_id: str | None,
    ) -> tuple[str, bool]:
        observation_id = str(uuid4())
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO observations
                    (id, data_source_id, collector_run_id, market, symbol,
                     effective_at, published_at, observed_at, source_url,
                     methodology_version, value_json, warnings_json, checksum, data_class)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, ?, ?)
                ON CONFLICT (data_source_id, checksum) DO NOTHING
                RETURNING id
                """,
                (
                    observation_id,
                    data_source_id,
                    collector_run_id,
                    observation.market,
                    observation.symbol,
                    observation.effective_at,
                    observation.published_at,
                    observation.observed_at,
                    observation.source_url,
                    observation.methodology_version,
                    json.dumps(observation.value, ensure_ascii=False, default=str),
                    json.dumps(observation.warnings, ensure_ascii=False),
                    observation.checksum,
                    observation.data_class.value,
                ),
            )
            inserted = cur.fetchone()
            if inserted:
                resolved_id = str(inserted["id"])
                created = True
            else:
                cur.execute(
                    "SELECT id FROM observations WHERE data_source_id = ? AND checksum = ?",
                    (data_source_id, observation.checksum),
                )
                existing = cur.fetchone()
                if not existing:
                    raise RuntimeError("observation_dedupe_lookup_failed")
                resolved_id = str(existing["id"])
                created = False
            db.commit()
            cur.close()
        return resolved_id, created

    def get_overview(
        self,
        *,
        user_id: int,
        as_of: str | None,
        market: str,
        data_class: str,
        watchlist_pairs: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        del user_id  # JWT scope is enforced at the route; snapshots are shared research data.
        params: list[Any] = [market, data_class]
        date_filter = ""
        if as_of:
            date_filter = "AND as_of::date = ?::date"
            params.append(as_of)
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                f"""
                SELECT id, as_of, market, status, methodology_version,
                       summary_json, evidence_checksum, data_class, created_at
                FROM insight_snapshots
                WHERE market = ? AND data_class = ? {date_filter}
                ORDER BY as_of DESC, created_at DESC
                LIMIT 1
                """,
                tuple(params),
            )
            snapshot = cur.fetchone()
            if not snapshot:
                cur.close()
                return {
                    "asOf": as_of,
                    "market": market,
                    "mode": data_class.lower(),
                    "status": "UNAVAILABLE",
                    "summary": {},
                    "opinions": [],
                }
            snapshot_id = str(snapshot["id"])
            cur.execute(
                """
                SELECT id, symbol, market, stance, score, confidence, rationale_json,
                       explanation, explanation_model, evidence_validated, data_class
                FROM asset_opinions
                WHERE insight_snapshot_id = ?
                ORDER BY confidence DESC, symbol ASC
                """,
                (snapshot_id,),
            )
            opinions = cur.fetchall() or []
            cur.execute(
                """
                SELECT l.asset_opinion_id, l.observation_id, l.evidence_role
                FROM insight_evidence_links l
                WHERE l.insight_snapshot_id = ?
                ORDER BY l.id ASC
                """,
                (snapshot_id,),
            )
            links = cur.fetchall() or []
            cur.close()

        if watchlist_pairs is not None:
            from .watchlist_scope import opinion_key

            watchlist_keys = {
                opinion_key(pair)
                for pair in watchlist_pairs
                if isinstance(pair, Mapping) and opinion_key(pair)
            }
            opinions = [
                row
                for row in opinions
                if opinion_key(row) in watchlist_keys
            ]
            retained_ids = {str(row["id"]) for row in opinions}
            links = [
                link
                for link in links
                if not link.get("asset_opinion_id")
                or str(link["asset_opinion_id"]) in retained_ids
            ]

        evidence_by_opinion: dict[str, list[dict[str, str]]] = {}
        for link in links:
            key = str(link.get("asset_opinion_id") or "snapshot")
            evidence_by_opinion.setdefault(key, []).append(
                {
                    "id": str(link["observation_id"]),
                    "role": str(link["evidence_role"]),
                }
            )
        return {
            "id": snapshot_id,
            "asOf": _iso(snapshot["as_of"]),
            "market": snapshot["market"],
            "mode": str(snapshot["data_class"]).lower(),
            "status": snapshot["status"],
            "methodologyVersion": snapshot["methodology_version"],
            "evidenceChecksum": snapshot["evidence_checksum"],
            "summary": _json_value(snapshot["summary_json"], {}),
            "opinions": [
                {
                    "id": str(row["id"]),
                    "symbol": row["symbol"],
                    "market": row["market"],
                    "stance": row["stance"],
                    "score": float(row["score"]) if row["score"] is not None else None,
                    "confidence": float(row["confidence"]),
                    "rationale": _json_value(row["rationale_json"], {}),
                    "explanation": row["explanation"],
                    "explanationModel": row["explanation_model"],
                    "evidenceValidated": bool(row["evidence_validated"]),
                    "dataClass": row["data_class"],
                    "evidence": evidence_by_opinion.get(str(row["id"]), []),
                }
                for row in opinions
            ],
            "evidence": evidence_by_opinion.get("snapshot", []),
        }

    def get_overview_all(
        self,
        *,
        user_id: int,
        as_of: str | None,
        data_class: str,
        watchlist_pairs: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Aggregate the latest market-scoped snapshots for the ALL selector."""
        views = [
            self.get_overview(
                user_id=user_id,
                as_of=as_of,
                market=market,
                data_class=data_class,
                watchlist_pairs=watchlist_pairs,
            )
            for market in ("crypto", "vn", "gold")
        ]
        available = [view for view in views if view.get("status") != "UNAVAILABLE"]
        if not available:
            return {
                "asOf": as_of,
                "market": "all",
                "mode": data_class.lower(),
                "status": "UNAVAILABLE",
                "summary": {},
                "opinions": [],
            }

        def unique_values(key: str) -> list[str]:
            result: list[str] = []
            for view in available:
                for value in view.get("summary", {}).get(key, []) or []:
                    value = str(value)
                    if value and value not in result:
                        result.append(value)
            return result

        sources = unique_values("sources")
        metrics = unique_values("metrics")
        opinions = [
            opinion
            for view in available
            for opinion in view.get("opinions", []) or []
        ]
        opinions.sort(
            key=lambda opinion: (
                -float(opinion.get("confidence") or 0),
                str(opinion.get("symbol") or ""),
            )
        )
        evidence: list[dict[str, str]] = []
        seen_evidence: set[str] = set()
        for view in available:
            for item in view.get("evidence", []) or []:
                evidence_id = str(item.get("id") or "")
                if evidence_id and evidence_id not in seen_evidence:
                    seen_evidence.add(evidence_id)
                    evidence.append({"id": evidence_id, "role": str(item.get("role") or "CONTEXT")})

        checksums = sorted(
            str(view.get("evidenceChecksum"))
            for view in available
            if view.get("evidenceChecksum")
        )
        aggregate_checksum = hashlib.sha256("|".join(checksums).encode("utf-8")).hexdigest()
        model_statuses = {
            str(view.get("summary", {}).get("directionalModelStatus") or "UNAVAILABLE")
            for view in available
        }
        directional_status = (
            next(iter(model_statuses))
            if len(model_statuses) == 1
            else "MIXED"
        )
        methodology_versions = list(
            dict.fromkeys(
                str(view.get("methodologyVersion"))
                for view in available
                if view.get("methodologyVersion")
            )
        )
        statuses = {str(view.get("status")) for view in available}
        status = "COMPLETE" if statuses == {"COMPLETE"} else "PARTIAL"
        as_of_values = [str(view.get("asOf")) for view in available if view.get("asOf")]

        return {
            "id": f"aggregate-{aggregate_checksum[:24]}",
            "asOf": max(as_of_values) if as_of_values else as_of,
            "market": "all",
            "mode": data_class.lower(),
            "status": status,
            "methodologyVersion": ",".join(methodology_versions),
            "evidenceChecksum": aggregate_checksum,
            "summary": {
                "sources": sources,
                "metrics": metrics,
                "sourceCount": len(sources),
                "metricCount": len(metrics),
                "observationCount": sum(
                    int(view.get("summary", {}).get("observationCount") or 0)
                    for view in available
                ),
                "directionalModelStatus": directional_status,
            },
            "opinions": opinions,
            "evidence": evidence,
        }

    def list_dates(self, *, market: str | None, data_class: str) -> list[str]:
        params: list[Any] = [data_class]
        market_filter = ""
        if market:
            market_filter = "AND market = ?"
            params.append(market)
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                f"""
                SELECT DISTINCT as_of::date AS snapshot_date
                FROM insight_snapshots
                WHERE data_class = ? {market_filter}
                ORDER BY snapshot_date DESC
                LIMIT 366
                """,
                tuple(params),
            )
            rows = cur.fetchall() or []
            cur.close()
        return [str(row["snapshot_date"]) for row in rows]

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT o.id, o.market, o.symbol, o.effective_at, o.published_at,
                       o.observed_at, o.source_url, o.methodology_version,
                       o.value_json, o.warnings_json, o.checksum, o.data_class,
                       s.code AS source_code, s.name AS source_name
                FROM observations o
                JOIN data_sources s ON s.id = o.data_source_id
                WHERE o.id = ?
                """,
                (evidence_id,),
            )
            row = cur.fetchone()
            cur.close()
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "market": row["market"],
            "symbol": row["symbol"],
            "source": row["source_code"],
            "sourceName": row["source_name"],
            "sourceUrl": row["source_url"],
            "effectiveAt": _iso(row["effective_at"]),
            "publishedAt": _iso(row["published_at"]),
            "observedAt": _iso(row["observed_at"]),
            "methodologyVersion": row["methodology_version"],
            "warnings": _json_value(row["warnings_json"], []),
            "checksum": row["checksum"],
            "dataClass": row["data_class"],
            "reliability": self._evidence_row(row)["reliability"],
            "value": _json_value(row["value_json"], {}),
        }

    def data_health(self) -> list[dict[str, Any]]:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT s.code, s.name, s.market, s.source_url, s.enabled,
                       s.activation_mode, s.verified_at, s.disabled_reason,
                       s.freshness_sla_minutes, s.methodology_version,
                       r.status AS last_status, r.finished_at, r.records_fetched,
                       r.records_persisted, r.error_code,
                       o.last_observed_at, o.live_observations_30d
                FROM data_sources s
                LEFT JOIN LATERAL (
                    SELECT status, finished_at, records_fetched, records_persisted, error_code
                    FROM collector_runs
                    WHERE data_source_id = s.id
                       OR (request_json->'sourceCodes') @> to_jsonb(ARRAY[s.code]::text[])
                    ORDER BY created_at DESC
                    LIMIT 1
                ) r ON TRUE
                LEFT JOIN LATERAL (
                    SELECT MAX(observed_at) AS last_observed_at,
                           COUNT(*) FILTER (
                               WHERE observed_at >= NOW() - INTERVAL '30 days'
                           ) AS live_observations_30d
                    FROM observations
                    WHERE data_source_id = s.id AND data_class = 'LIVE'
                ) o ON TRUE
                ORDER BY s.market, s.code
                """
            )
            rows = cur.fetchall() or []
            cur.close()
        return [
            {
                "code": row["code"],
                "name": row["name"],
                "market": row["market"],
                "sourceUrl": row["source_url"],
                "enabled": bool(row["enabled"]),
                "activationMode": row["activation_mode"],
                "verifiedAt": _iso(row["verified_at"]),
                "disabledReason": row["disabled_reason"],
                "freshnessSlaMinutes": row["freshness_sla_minutes"],
                "methodologyVersion": row["methodology_version"],
                "lastObservedAt": _iso(row["last_observed_at"]),
                "freshness": classify_freshness(
                    row["last_observed_at"],
                    sla_minutes=int(row["freshness_sla_minutes"]),
                ),
                "coverage": {"liveObservations30d": int(row["live_observations_30d"] or 0)},
                "lastRun": {
                    "status": row["last_status"],
                    "finishedAt": _iso(row["finished_at"]),
                    "recordsFetched": row["records_fetched"],
                    "recordsPersisted": row["records_persisted"],
                    "errorCode": row["error_code"],
                }
                if row["last_status"]
                else None,
            }
            for row in rows
        ]


__all__ = ["SmartInsightsRepository"]
