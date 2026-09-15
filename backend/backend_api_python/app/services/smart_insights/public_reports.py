"""Safe, tenant-free storage for guest-facing research reports."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Mapping

from app.utils.db import get_db_connection


PUBLIC_GUEST_ASSET_SCOPE: tuple[dict[str, str], ...] = (
    {"market": "Crypto", "symbol": "BTC/USDT", "displaySymbol": "BTC"},
    {"market": "Crypto", "symbol": "SOL/USDT", "displaySymbol": "SOL"},
    {"market": "Crypto", "symbol": "LINK/USDT", "displaySymbol": "LINK"},
    {"market": "Forex", "symbol": "XAUUSD", "displaySymbol": "XAU"},
)
# Keep the guest market and guest research scopes aligned. Vietnamese equities
# can be added later when their dedicated research pipeline is ready.
PUBLIC_RESEARCH_ASSET_SCOPE: tuple[dict[str, str], ...] = PUBLIC_GUEST_ASSET_SCOPE
# Smart Insights publishes one reusable TradingAgents report per period. Fast
# Analysis remains available to the AI Assistant, but is not a second report
# product or scheduled LLM cost centre here.
PUBLIC_RESEARCH_REPORT_KINDS = frozenset({"deep"})
PUBLIC_RESEARCH_LOCALE = "vi-VN"
_PAYLOAD_FIELDS = frozenset(
    {"title", "summary", "body", "sections", "decision", "confidence", "provenance"}
)


def public_asset_key(asset: Mapping[str, Any]) -> str:
    return f"{str(asset.get('market') or '').strip().lower()}:{str(asset.get('symbol') or '').strip()}"


PUBLIC_RESEARCH_ASSET_KEYS = frozenset(
    public_asset_key(asset) for asset in PUBLIC_RESEARCH_ASSET_SCOPE
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


class PublicResearchReportsRepository:
    """Persist public reports without touching account-owned history tables."""

    def latest_completed(self, *, asset_key: str, report_kind: str, locale: str) -> dict[str, Any] | None:
        return self._latest(asset_key=asset_key, report_kind=report_kind, locale=locale, completed_only=True)

    def latest_status(self, *, asset_key: str, report_kind: str, locale: str) -> dict[str, Any] | None:
        return self._latest(asset_key=asset_key, report_kind=report_kind, locale=locale, completed_only=False)

    def current(self, *, asset_key: str, report_kind: str, locale: str, effective_date: date | str) -> dict[str, Any] | None:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    SELECT asset_key, report_kind, locale, effective_date, status,
                           payload_json, generated_at
                    FROM public_research_reports
                    WHERE asset_key = ? AND report_kind = ? AND locale = ? AND effective_date = ?
                    LIMIT 1
                    """,
                    (asset_key, report_kind, locale, _iso_date(effective_date)),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                cur.close()

    def claim_pending(self, *, asset_key: str, report_kind: str, locale: str, effective_date: date | str) -> bool:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO public_research_reports
                    (asset_key, report_kind, locale, effective_date, status, payload_json)
                    VALUES (?, ?, ?, ?, 'pending', '{}'::jsonb)
                    ON CONFLICT (asset_key, report_kind, locale, effective_date) DO NOTHING
                    RETURNING id
                    """,
                    (asset_key, report_kind, locale, _iso_date(effective_date)),
                )
                claimed = cur.fetchone() is not None
                db.commit()
                return claimed
            finally:
                cur.close()

    def mark_pending(
        self,
        *,
        asset_key: str,
        report_kind: str,
        locale: str,
        effective_date: date | str,
        source_run_id: str | None = None,
    ) -> None:
        self._upsert(
            asset_key=asset_key,
            report_kind=report_kind,
            locale=locale,
            effective_date=effective_date,
            status="pending",
            source_run_id=source_run_id,
        )

    def mark_complete(
        self,
        *,
        asset_key: str,
        report_kind: str,
        locale: str,
        effective_date: date | str,
        payload: Mapping[str, Any],
        source_run_id: str | None = None,
    ) -> None:
        self._upsert(
            asset_key=asset_key,
            report_kind=report_kind,
            locale=locale,
            effective_date=effective_date,
            status="complete",
            payload=payload,
            source_run_id=source_run_id,
        )

    def mark_failed(
        self,
        *,
        asset_key: str,
        report_kind: str,
        locale: str,
        effective_date: date | str,
        failure_code: str,
        source_run_id: str | None = None,
    ) -> None:
        self._upsert(
            asset_key=asset_key,
            report_kind=report_kind,
            locale=locale,
            effective_date=effective_date,
            status="failed",
            failure_code=failure_code,
            source_run_id=source_run_id,
        )

    def list_pending_deep(self, *, locale: str) -> list[dict[str, Any]]:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    SELECT asset_key, report_kind, locale, effective_date, status, source_run_id
                    FROM public_research_reports
                    WHERE report_kind = 'deep' AND locale = ? AND status = 'pending'
                      AND source_run_id IS NOT NULL
                    ORDER BY effective_date ASC, id ASC
                    """,
                    (locale,),
                )
                return [dict(row) for row in (cur.fetchall() or [])]
            finally:
                cur.close()

    def _upsert(
        self,
        *,
        asset_key: str,
        report_kind: str,
        locale: str,
        effective_date: date | str,
        status: str,
        payload: Mapping[str, Any] | None = None,
        failure_code: str | None = None,
        source_run_id: str | None = None,
    ) -> None:
        clean_payload = json.dumps(dict(payload or {}), ensure_ascii=False) if payload is not None else None
        clean_failure = str(failure_code or "").strip()[:80] or None
        clean_run_id = str(source_run_id or "").strip()[:128] or None
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO public_research_reports
                    (asset_key, report_kind, locale, effective_date, status, payload_json, failure_code, source_run_id, generated_at)
                    VALUES (?, ?, ?, ?, ?, ?::jsonb, ?, ?, CASE WHEN ? = 'complete' THEN NOW() ELSE NULL END)
                    ON CONFLICT (asset_key, report_kind, locale, effective_date) DO UPDATE
                    SET status = EXCLUDED.status,
                        payload_json = EXCLUDED.payload_json,
                        failure_code = EXCLUDED.failure_code,
                        source_run_id = COALESCE(EXCLUDED.source_run_id, public_research_reports.source_run_id),
                        generated_at = EXCLUDED.generated_at,
                        updated_at = NOW()
                    """,
                    (
                        asset_key,
                        report_kind,
                        locale,
                        _iso_date(effective_date),
                        status,
                        clean_payload,
                        clean_failure,
                        clean_run_id,
                        status,
                    ),
                )
                db.commit()
            finally:
                cur.close()

    def _latest(self, *, asset_key: str, report_kind: str, locale: str, completed_only: bool) -> dict[str, Any] | None:
        status_clause = "AND status = 'complete'" if completed_only else ""
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    f"""
                    SELECT asset_key, report_kind, locale, effective_date, status,
                           payload_json, generated_at
                    FROM public_research_reports
                    WHERE asset_key = ? AND report_kind = ? AND locale = ?
                    {status_clause}
                    ORDER BY effective_date DESC, id DESC
                    LIMIT 1
                    """,
                    (asset_key, report_kind, locale),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                cur.close()


class PublicResearchReportsService:
    def __init__(self, repository: PublicResearchReportsRepository | None = None) -> None:
        self.repository = repository or PublicResearchReportsRepository()

    @staticmethod
    def _validate(asset_key: str, report_kind: str, locale: str) -> tuple[str, str, str]:
        clean_key = str(asset_key or "").strip()
        clean_kind = str(report_kind or "").strip().lower()
        # Guest reports are published once in the canonical product language.
        # The UI may still send en-US (or another supported display locale), so
        # treat the requested locale as an advisory value and read the
        # tenant-free canonical row instead of returning a misleading 404.
        clean_locale = PUBLIC_RESEARCH_LOCALE
        if clean_key not in PUBLIC_RESEARCH_ASSET_KEYS:
            raise ValueError("unsupported_public_asset")
        if clean_kind not in PUBLIC_RESEARCH_REPORT_KINDS:
            raise ValueError("unsupported_public_report_kind")
        return clean_key, clean_kind, clean_locale

    @staticmethod
    def public_projection(row: Mapping[str, Any], *, is_fallback: bool = False) -> dict[str, Any]:
        # The repository selects PostgreSQL's payload_json column directly;
        # keep payload as a compatibility fallback for lightweight adapters.
        payload = row.get("payload_json", row.get("payload")) if isinstance(row, Mapping) else {}
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
            "effectiveDate": _iso_date(row.get("effective_date")),
            "generatedAt": str(row.get("generated_at") or ""),
            "isFallback": bool(is_fallback),
        }
        for key in _PAYLOAD_FIELDS:
            if key in payload and (safe_value := _safe_value(payload[key])) is not None:
                result[key] = safe_value
        return result

    def get_latest(self, asset_key: str, report_kind: str, locale: str = PUBLIC_RESEARCH_LOCALE) -> dict[str, Any] | None:
        clean_key, clean_kind, clean_locale = self._validate(asset_key, report_kind, locale)
        latest_status = self.repository.latest_status(
            asset_key=clean_key, report_kind=clean_kind, locale=clean_locale
        )
        latest_completed = self.repository.latest_completed(
            asset_key=clean_key, report_kind=clean_kind, locale=clean_locale
        )
        if latest_completed is None:
            return None
        is_fallback = bool(
            latest_status
            and (
                str(latest_status.get("status") or "") != "complete"
                or _iso_date(latest_status.get("effective_date")) != _iso_date(latest_completed.get("effective_date"))
            )
        )
        return self.public_projection(latest_completed, is_fallback=is_fallback)

    def get_state(
        self,
        asset_key: str,
        report_kind: str,
        *,
        effective_date: date | str,
        locale: str = PUBLIC_RESEARCH_LOCALE,
    ) -> dict[str, Any]:
        clean_key, clean_kind, clean_locale = self._validate(asset_key, report_kind, locale)
        current = self.repository.current(
            asset_key=clean_key, report_kind=clean_kind, locale=clean_locale,
            effective_date=effective_date,
        )
        latest = self.repository.latest_completed(
            asset_key=clean_key, report_kind=clean_kind, locale=clean_locale,
        )
        if current:
            status = str(current.get("status") or "pending")
            report = self.public_projection(current) if status == "complete" else (
                self.public_projection(latest, is_fallback=True) if latest else None
            )
            return {
                "assetKey": clean_key,
                "reportKind": clean_kind,
                "periodKey": _iso_date(effective_date),
                "status": status,
                "canCreate": False,
                "report": report,
            }
        return {
            "assetKey": clean_key,
            "reportKind": clean_kind,
            "periodKey": _iso_date(effective_date),
            "status": "missing",
            "canCreate": True,
            "report": self.public_projection(latest, is_fallback=True) if latest else None,
        }


__all__ = [
    "PUBLIC_GUEST_ASSET_SCOPE",
    "PUBLIC_RESEARCH_ASSET_KEYS",
    "PUBLIC_RESEARCH_ASSET_SCOPE",
    "PUBLIC_RESEARCH_LOCALE",
    "PUBLIC_RESEARCH_REPORT_KINDS",
    "PublicResearchReportsRepository",
    "PublicResearchReportsService",
    "public_asset_key",
]
