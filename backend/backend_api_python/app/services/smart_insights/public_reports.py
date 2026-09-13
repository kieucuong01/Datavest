"""Safe, tenant-free storage for guest-facing research reports."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Mapping

from app.utils.db import get_db_connection


PUBLIC_RESEARCH_ASSET_SCOPE: tuple[dict[str, str], ...] = (
    {"market": "Crypto", "symbol": "BTC/USDT", "displaySymbol": "BTC"},
    {"market": "VNStock", "symbol": "VNINDEX", "displaySymbol": "VNINDEX"},
    {"market": "Forex", "symbol": "XAUUSD", "displaySymbol": "XAU"},
)
PUBLIC_RESEARCH_REPORT_KINDS = frozenset({"quick", "deep"})
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
        clean_locale = str(locale or PUBLIC_RESEARCH_LOCALE).strip() or PUBLIC_RESEARCH_LOCALE
        if clean_key not in PUBLIC_RESEARCH_ASSET_KEYS:
            raise ValueError("unsupported_public_asset")
        if clean_kind not in PUBLIC_RESEARCH_REPORT_KINDS:
            raise ValueError("unsupported_public_report_kind")
        if clean_locale != PUBLIC_RESEARCH_LOCALE:
            raise ValueError("unsupported_public_report_locale")
        return clean_key, clean_kind, clean_locale

    @staticmethod
    def public_projection(row: Mapping[str, Any], *, is_fallback: bool = False) -> dict[str, Any]:
        payload = row.get("payload") if isinstance(row, Mapping) else {}
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


__all__ = [
    "PUBLIC_RESEARCH_ASSET_KEYS",
    "PUBLIC_RESEARCH_ASSET_SCOPE",
    "PUBLIC_RESEARCH_LOCALE",
    "PUBLIC_RESEARCH_REPORT_KINDS",
    "PublicResearchReportsRepository",
    "PublicResearchReportsService",
    "public_asset_key",
]
