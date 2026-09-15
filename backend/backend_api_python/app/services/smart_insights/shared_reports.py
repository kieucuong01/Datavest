"""Reusable report storage for authenticated watchlist assets.

This module deliberately stores no recipient or initiator information. Route
authorization checks the caller's *current* watchlist before returning a row.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Mapping

from app.services.smart_insights.public_reports import (
    PUBLIC_RESEARCH_LOCALE,
    PUBLIC_RESEARCH_REPORT_KINDS,
)
from app.utils.db import get_db_connection


_PAYLOAD_FIELDS = frozenset(
    {"title", "summary", "body", "sections", "decision", "confidence", "provenance"}
)


def _iso_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_safe_value(item) for item in value][:80]
    if isinstance(value, Mapping):
        return {str(key)[:80]: _safe_value(item) for key, item in list(value.items())[:80]}
    return None


def reporting_period_key(report_kind: str, *, today: date | None = None) -> str:
    """Return the Monday of the Vietnamese calendar week for deep research."""
    current = today or date.today()
    kind = str(report_kind or "").strip().lower()
    if kind not in PUBLIC_RESEARCH_REPORT_KINDS:
        raise ValueError("unsupported_shared_report_kind")
    return (current - timedelta(days=current.weekday())).isoformat()


class SharedResearchReportsRepository:
    """PostgreSQL repository with an atomic pending-period claim."""

    def current(self, *, asset_key: str, report_kind: str, locale: str, period_key: str) -> dict[str, Any] | None:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    SELECT asset_key, report_kind, locale, period_key, status,
                           payload_json, generated_at
                    FROM shared_watchlist_research_reports
                    WHERE asset_key = ? AND report_kind = ? AND locale = ? AND period_key = ?
                    LIMIT 1
                    """,
                    (asset_key, report_kind, locale, period_key),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                cur.close()

    def latest_completed(self, *, asset_key: str, report_kind: str, locale: str) -> dict[str, Any] | None:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    SELECT asset_key, report_kind, locale, period_key, status,
                           payload_json, generated_at
                    FROM shared_watchlist_research_reports
                    WHERE asset_key = ? AND report_kind = ? AND locale = ? AND status = 'complete'
                    ORDER BY period_key DESC, id DESC
                    LIMIT 1
                    """,
                    (asset_key, report_kind, locale),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                cur.close()

    def claim_pending(self, *, asset_key: str, report_kind: str, locale: str, period_key: str) -> bool:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO shared_watchlist_research_reports
                    (asset_key, report_kind, locale, period_key, status, payload_json)
                    VALUES (?, ?, ?, ?, 'pending', '{}'::jsonb)
                    ON CONFLICT (asset_key, report_kind, locale, period_key) DO NOTHING
                    RETURNING id
                    """,
                    (asset_key, report_kind, locale, period_key),
                )
                claimed = cur.fetchone() is not None
                db.commit()
                return claimed
            finally:
                cur.close()

    def mark_complete(
        self, *, asset_key: str, report_kind: str, locale: str, period_key: str,
        payload: Mapping[str, Any], source_run_id: str | None = None,
    ) -> None:
        self._update(
            asset_key=asset_key, report_kind=report_kind, locale=locale, period_key=period_key,
            status="complete", payload=payload, source_run_id=source_run_id,
        )

    def mark_failed(
        self, *, asset_key: str, report_kind: str, locale: str, period_key: str,
        failure_code: str, source_run_id: str | None = None,
    ) -> None:
        self._update(
            asset_key=asset_key, report_kind=report_kind, locale=locale, period_key=period_key,
            status="failed", failure_code=failure_code, source_run_id=source_run_id,
        )

    def set_source_run(
        self, *, asset_key: str, report_kind: str, locale: str, period_key: str, source_run_id: str,
    ) -> None:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    UPDATE shared_watchlist_research_reports
                    SET source_run_id = ?, updated_at = NOW()
                    WHERE asset_key = ? AND report_kind = ? AND locale = ? AND period_key = ?
                      AND status = 'pending'
                    """,
                    (str(source_run_id)[:128], asset_key, report_kind, locale, period_key),
                )
                db.commit()
            finally:
                cur.close()

    def list_pending_deep(self, *, locale: str) -> list[dict[str, Any]]:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    SELECT asset_key, report_kind, locale, period_key, status, source_run_id
                    FROM shared_watchlist_research_reports
                    WHERE report_kind = 'deep' AND locale = ? AND status = 'pending'
                      AND source_run_id IS NOT NULL
                    ORDER BY period_key ASC, id ASC
                    """,
                    (locale,),
                )
                return [dict(row) for row in (cur.fetchall() or [])]
            finally:
                cur.close()

    def _update(
        self, *, asset_key: str, report_kind: str, locale: str, period_key: str,
        status: str, payload: Mapping[str, Any] | None = None, failure_code: str | None = None,
        source_run_id: str | None = None,
    ) -> None:
        clean_payload = json.dumps(dict(payload or {}), ensure_ascii=False) if payload is not None else None
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    UPDATE shared_watchlist_research_reports
                    SET status = ?, payload_json = COALESCE(?::jsonb, payload_json),
                        failure_code = ?, source_run_id = COALESCE(?, source_run_id),
                        generated_at = CASE WHEN ? = 'complete' THEN NOW() ELSE generated_at END,
                        updated_at = NOW()
                    WHERE asset_key = ? AND report_kind = ? AND locale = ? AND period_key = ?
                    """,
                    (
                        status, clean_payload, str(failure_code or "")[:80] or None,
                        str(source_run_id or "")[:128] or None, status,
                        asset_key, report_kind, locale, period_key,
                    ),
                )
                db.commit()
            finally:
                cur.close()


class SharedResearchReportsService:
    def __init__(self, repository: SharedResearchReportsRepository | None = None) -> None:
        self.repository = repository or SharedResearchReportsRepository()

    @staticmethod
    def _validate(asset_key: str, report_kind: str) -> tuple[str, str]:
        key = str(asset_key or "").strip()
        kind = str(report_kind or "").strip().lower()
        if not key or ":" not in key or len(key) > 120:
            raise ValueError("invalid_shared_asset")
        if kind not in PUBLIC_RESEARCH_REPORT_KINDS:
            raise ValueError("unsupported_shared_report_kind")
        return key, kind

    @staticmethod
    def project(row: Mapping[str, Any]) -> dict[str, Any]:
        payload = row.get("payload_json", row.get("payload")) or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError):
                payload = {}
        payload = payload if isinstance(payload, Mapping) else {}
        result = {
            "assetKey": str(row.get("asset_key") or ""),
            "reportKind": str(row.get("report_kind") or ""),
            "locale": str(row.get("locale") or PUBLIC_RESEARCH_LOCALE),
            "effectiveDate": _iso_date(row.get("period_key")),
            "generatedAt": str(row.get("generated_at") or ""),
        }
        for key in _PAYLOAD_FIELDS:
            if key in payload and (safe_value := _safe_value(payload[key])) is not None:
                result[key] = safe_value
        return result

    def state(self, asset_key: str, report_kind: str, *, today: date | None = None) -> dict[str, Any]:
        key, kind = self._validate(asset_key, report_kind)
        period = reporting_period_key(kind, today=today)
        current = self.repository.current(
            asset_key=key, report_kind=kind, locale=PUBLIC_RESEARCH_LOCALE, period_key=period
        )
        latest = self.repository.latest_completed(
            asset_key=key, report_kind=kind, locale=PUBLIC_RESEARCH_LOCALE
        )
        if current:
            status = str(current.get("status") or "pending")
            report = self.project(current) if status == "complete" else (self.project(latest) if latest else None)
            return {
                "assetKey": key, "reportKind": kind, "periodKey": period,
                "status": status, "canCreate": False, "report": report,
            }
        return {
            "assetKey": key, "reportKind": kind, "periodKey": period,
            "status": "missing", "canCreate": True,
            "report": self.project(latest) if latest else None,
        }

    def claim(self, asset_key: str, report_kind: str, *, today: date | None = None) -> dict[str, Any]:
        key, kind = self._validate(asset_key, report_kind)
        period = reporting_period_key(kind, today=today)
        claimed = self.repository.claim_pending(
            asset_key=key, report_kind=kind, locale=PUBLIC_RESEARCH_LOCALE, period_key=period
        )
        state = self.state(key, kind, today=today)
        return {**state, "claimed": claimed}


__all__ = [
    "SharedResearchReportsRepository",
    "SharedResearchReportsService",
    "reporting_period_key",
]
