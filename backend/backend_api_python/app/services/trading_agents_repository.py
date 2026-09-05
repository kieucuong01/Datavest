"""Durable, owner-scoped persistence for private TradingAgents runs."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, Mapping

from app.utils.db import get_db_connection


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_RUN_STATUSES = frozenset({"queued", "running", "succeeded", "failed", "cancelled"})
_SENSITIVE_FAILURE_PARTS = ("authorization", "cookie", "password", "secret", "token", "traceback", "stack trace")
_SAFE_FAILURE_MESSAGE = "TradingAgents service failed; inspect private service logs."


class TradingAgentsRepository:
    """Keep DataVest's run index separate from the service's native files."""

    def create_run(
        self,
        *,
        user_id: int,
        request: Mapping[str, Any],
        config: Mapping[str, Any],
        source_pin: str,
        config_checksum: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        clean_user_id = int(user_id)
        if clean_user_id <= 0:
            raise ValueError("user_id must be positive")
        clean_run_id = self._validate_run_id(run_id or uuid.uuid4().hex)
        clean_source_pin = str(source_pin or "").strip()
        if not clean_source_pin or len(clean_source_pin) > 160:
            raise ValueError("source_pin is required and must be at most 160 characters")
        request_json = self._json_mapping(request, "request")
        config_json = self._json_mapping(config, "config")
        clean_checksum = (config_checksum or self._checksum(config_json)).lower()
        if not _SHA256_RE.fullmatch(clean_checksum):
            raise ValueError("config_checksum must be a lowercase SHA-256 digest")

        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO trading_agents_runs
                    (run_id, user_id, status, request_json, config_json, config_checksum, source_pin, created_at)
                    VALUES (?, ?, 'queued', ?::jsonb, ?::jsonb, ?, ?, NOW())
                    """,
                    (
                        clean_run_id,
                        clean_user_id,
                        request_json,
                        config_json,
                        clean_checksum,
                        clean_source_pin,
                    ),
                )
                db.commit()
            finally:
                cur.close()
        return {
            "run_id": clean_run_id,
            "user_id": clean_user_id,
            "status": "queued",
            "config_checksum": clean_checksum,
            "source_pin": clean_source_pin,
        }

    def append_event(
        self,
        *,
        run_id: str,
        sequence: int,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        clean_run_id = self._validate_run_id(run_id)
        clean_sequence = self._validate_sequence(sequence)
        clean_event_type = self._validate_event_type(event_type)
        payload_json = self._json_mapping(payload, "payload")

        with get_db_connection() as db:
            cur = db.cursor()
            try:
                # The callback cannot choose an owner: it is derived from the
                # durable run row it is appending to.
                cur.execute(
                    """
                    INSERT INTO trading_agents_events
                    (run_id, user_id, sequence, event_type, payload_json, created_at)
                    SELECT ?, user_id, ?, ?, ?::jsonb, NOW()
                    FROM trading_agents_runs
                    WHERE run_id = ?
                    """,
                    (clean_run_id, clean_sequence, clean_event_type, payload_json, clean_run_id),
                )
                db.commit()
            finally:
                cur.close()

    def store_artifact(
        self,
        *,
        run_id: str,
        artifact_name: str,
        storage_path: str,
        sha256: str,
        byte_size: int,
        content_type: str = "text/markdown",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        clean_run_id = self._validate_run_id(run_id)
        clean_name = self._validate_short_text(artifact_name, "artifact_name", 160)
        clean_path = self._validate_short_text(storage_path, "storage_path", 1024)
        clean_content_type = self._validate_short_text(content_type, "content_type", 120)
        clean_sha256 = str(sha256 or "").lower()
        if not _SHA256_RE.fullmatch(clean_sha256):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        if isinstance(byte_size, bool) or int(byte_size) < 0:
            raise ValueError("byte_size must be non-negative")
        metadata_json = self._json_mapping(metadata or {}, "metadata")

        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO trading_agents_artifacts
                    (run_id, user_id, artifact_name, content_type, storage_path, sha256, byte_size, metadata_json)
                    SELECT ?, user_id, ?, ?, ?, ?, ?, ?::jsonb
                    FROM trading_agents_runs
                    WHERE run_id = ?
                    ON CONFLICT (run_id, artifact_name) DO NOTHING
                    """,
                    (
                        clean_run_id,
                        clean_name,
                        clean_content_type,
                        clean_path,
                        clean_sha256,
                        int(byte_size),
                        metadata_json,
                        clean_run_id,
                    ),
                )
                db.commit()
            finally:
                cur.close()

    def transition_run(
        self,
        *,
        run_id: str,
        status: str,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> None:
        clean_run_id = self._validate_run_id(run_id)
        clean_status = str(status or "").strip().lower()
        if clean_status not in _RUN_STATUSES:
            raise ValueError("unsupported TradingAgents run status")
        clean_code = self._safe_failure_code(failure_code)
        clean_message = self._safe_failure_message(failure_message)

        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    UPDATE trading_agents_runs
                    SET status = ?,
                        started_at = CASE WHEN ? = 'running' AND started_at IS NULL THEN NOW() ELSE started_at END,
                        finished_at = CASE WHEN ? IN ('succeeded', 'failed', 'cancelled') THEN NOW() ELSE finished_at END,
                        failure_code = ?,
                        failure_message = ?
                    WHERE run_id = ?
                    """,
                    (clean_status, clean_status, clean_status, clean_code, clean_message, clean_run_id),
                )
                db.commit()
            finally:
                cur.close()

    def get_owned_run(self, *, user_id: int, run_id: str) -> dict[str, Any] | None:
        clean_run_id = self._validate_run_id(run_id)
        clean_user_id = int(user_id)
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    SELECT run_id, user_id, status, request_json, config_json, config_checksum, source_pin,
                           failure_code, failure_message, created_at, started_at, finished_at
                    FROM trading_agents_runs
                    WHERE run_id = ? AND user_id = ?
                    """,
                    (clean_run_id, clean_user_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                result = dict(row)
                cur.execute(
                    """
                    SELECT sequence, event_type, payload_json, created_at
                    FROM trading_agents_events
                    WHERE run_id = ? AND user_id = ?
                    ORDER BY sequence ASC
                    """,
                    (clean_run_id, clean_user_id),
                )
                result["events"] = [dict(item) for item in (cur.fetchall() or [])]
                cur.execute(
                    """
                    SELECT artifact_name, content_type, storage_path, sha256, byte_size, metadata_json, created_at
                    FROM trading_agents_artifacts
                    WHERE run_id = ? AND user_id = ?
                    ORDER BY artifact_name ASC
                    """,
                    (clean_run_id, clean_user_id),
                )
                result["artifacts"] = [dict(item) for item in (cur.fetchall() or [])]
                cur.execute(
                    """
                    SELECT native_decision, native_rating, proposal_json, report_sha256, created_at
                    FROM trading_agents_proposals
                    WHERE run_id = ? AND user_id = ?
                    """,
                    (clean_run_id, clean_user_id),
                )
                proposal = cur.fetchone()
                result["proposal"] = dict(proposal) if proposal else None
                return result
            finally:
                cur.close()

    def get_run_for_worker(self, *, run_id: str) -> dict[str, Any] | None:
        """Load one durable run for a trusted Celery worker only.

        Human routes must use :meth:`get_owned_run`; this method deliberately
        stays in the private task boundary where there is no caller-supplied
        user identity to authorize.
        """
        clean_run_id = self._validate_run_id(run_id)
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    SELECT run_id, user_id, status, request_json, config_json, config_checksum, source_pin,
                           failure_code, failure_message, created_at, started_at, finished_at
                    FROM trading_agents_runs
                    WHERE run_id = ?
                    """,
                    (clean_run_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                cur.close()

    @staticmethod
    def _validate_run_id(value: str) -> str:
        clean_value = str(value or "").strip()
        if not _RUN_ID_RE.fullmatch(clean_value):
            raise ValueError("invalid TradingAgents run_id")
        return clean_value

    @staticmethod
    def _validate_sequence(value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("sequence must be a positive integer")
        try:
            clean_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("sequence must be a positive integer") from exc
        if clean_value <= 0 or clean_value > 2_147_483_647:
            raise ValueError("sequence must be a positive integer")
        return clean_value

    @staticmethod
    def _validate_event_type(value: str) -> str:
        clean_value = str(value or "").strip().lower()
        if not _EVENT_TYPE_RE.fullmatch(clean_value):
            raise ValueError("invalid TradingAgents event_type")
        return clean_value

    @staticmethod
    def _validate_short_text(value: str, name: str, limit: int) -> str:
        clean_value = str(value or "").strip()
        if not clean_value or len(clean_value) > limit:
            raise ValueError(f"{name} is required and must be at most {limit} characters")
        return clean_value

    @staticmethod
    def _optional_text(value: str | None, limit: int) -> str | None:
        if value is None:
            return None
        clean_value = str(value).strip()
        return clean_value[:limit] if clean_value else None

    @staticmethod
    def _safe_failure_code(value: str | None) -> str | None:
        clean_value = TradingAgentsRepository._optional_text(value, 80)
        if clean_value and any(part in clean_value.lower() for part in _SENSITIVE_FAILURE_PARTS):
            return "service_failure"
        return clean_value

    @staticmethod
    def _safe_failure_message(value: str | None) -> str | None:
        clean_value = TradingAgentsRepository._optional_text(value, 500)
        if clean_value and any(part in clean_value.lower() for part in _SENSITIVE_FAILURE_PARTS):
            return _SAFE_FAILURE_MESSAGE
        return clean_value

    @staticmethod
    def _json_mapping(value: Mapping[str, Any], name: str) -> str:
        if not isinstance(value, Mapping):
            raise ValueError(f"{name} must be an object")
        return json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _checksum(serialized_json: str) -> str:
        return hashlib.sha256(serialized_json.encode("utf-8")).hexdigest()
