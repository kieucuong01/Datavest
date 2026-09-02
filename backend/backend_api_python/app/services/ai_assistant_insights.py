"""Smart Insights projections backed only by AI Assistant analysis history.

This module deliberately contains no market scoring, snapshot materialisation or
evidence collector logic.  It presents the analysis that a user has already
asked AI Assistant to produce, pinned to the requested calendar day.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any, Iterable

MAX_BRIEF_WORDS = 600


def canonical_market(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    return {
        "CRYPTO": "crypto",
        "VNSTOCK": "vn",
        "FOREX": "gold",
        "GOLD": "gold",
    }.get(normalized, str(value or "").strip().lower())


def canonical_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if symbol in {"XAUUSD", "GOLD"}:
        return "XAU"
    return re.sub(r"[/:_-](USDT|USD)$", "", symbol)


def report_identity(report: dict[str, Any]) -> str:
    return f"{canonical_market(report.get('market'))}:{canonical_symbol(report.get('symbol'))}"


def _report_day(report: dict[str, Any]) -> str:
    value = str(report.get("created_at") or report.get("createdAt") or "")
    return value[:10]


def _timestamp(report: dict[str, Any]) -> str:
    return str(report.get("created_at") or report.get("createdAt") or "")


def select_watchlist_reports_for_date(
    watchlist: Iterable[dict[str, Any]], reports: Iterable[dict[str, Any]], as_of: str
) -> dict[str, dict[str, Any] | None]:
    """Return the newest completed report per watched asset for one exact day.

    This intentionally does *not* fall back to another day: presenting a newer
    report after the user changed ``as_of`` was the historical Smart Insights bug.
    """
    wanted = {
        report_identity(item)
        for item in watchlist
        if canonical_market(item.get("market")) and canonical_symbol(item.get("symbol"))
    }
    selected: dict[str, dict[str, Any] | None] = {key: None for key in wanted}
    for report in reports:
        if str(report.get("status") or report.get("task_status") or "completed").lower() != "completed":
            continue
        if _report_day(report) != as_of:
            continue
        key = report_identity(report)
        if key not in selected:
            continue
        current = selected[key]
        if current is None or _timestamp(report) > _timestamp(current) or (
            _timestamp(report) == _timestamp(current) and int(report.get("id") or 0) > int(current.get("id") or 0)
        ):
            selected[key] = report
    return selected


def _short_text(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def build_daily_brief(reports: Iterable[dict[str, Any]], as_of: str, locale: str = "vi-VN") -> dict[str, Any]:
    """Condense already-generated AI Assistant reports without another AI call."""
    completed = [item for item in reports if item and str(item.get("status") or "completed").lower() == "completed"]
    completed.sort(key=lambda item: (canonical_market(item.get("market")), canonical_symbol(item.get("symbol"))))
    source_ids = [int(item["id"]) for item in completed if item.get("id") is not None]
    checksum_input = "|".join(
        f"{item.get('id')}:{_timestamp(item)}:{item.get('decision')}:{item.get('confidence')}" for item in completed
    )
    checksum = hashlib.sha256(checksum_input.encode("utf-8")).hexdigest() if checksum_input else ""
    if not completed:
        is_vi = str(locale).lower().startswith("vi")
        return {
            "status": "UNAVAILABLE",
            "asOf": as_of,
            "assetCount": 0,
            "sourceAnalysisIds": [],
            "sourceChecksum": "",
            "content": "Chưa có nhận định từ AI Assistant cho ngày đã chọn." if is_vi else "No AI Assistant analysis is available for the selected date.",
        }

    is_vi = str(locale).lower().startswith("vi")
    intro = (
        f"Bản tin ngày {as_of}, tổng hợp từ {len(completed)} nhận định đã hoàn tất trong AI Assistant."
        if is_vi
        else f"Daily brief for {as_of}, compiled from {len(completed)} completed AI Assistant analyses."
    )
    budget = max(80, (MAX_BRIEF_WORDS - len(intro.split()) - len(completed) * 6) * 6)
    per_report = max(80, min(260, budget // max(1, len(completed))))
    lines = [intro]
    for item in completed:
        symbol = canonical_symbol(item.get("symbol")) or str(item.get("symbol") or "?")
        decision = str(item.get("decision") or "HOLD").upper()
        confidence = item.get("confidence")
        confidence_text = f" · {confidence}%" if confidence is not None else ""
        summary = _short_text(item.get("summary") or item.get("reasoning"), per_report)
        if is_vi:
            lines.append(f"{symbol}: {decision}{confidence_text}. {summary or 'Chưa có phần tóm tắt chi tiết.'}")
        else:
            lines.append(f"{symbol}: {decision}{confidence_text}. {summary or 'No detailed summary was returned.'}")
    content = "\n".join(lines)
    words = content.split()
    if len(words) > MAX_BRIEF_WORDS:
        content = " ".join(words[:MAX_BRIEF_WORDS]).rstrip(".,;:") + "…"
    return {
        "status": "AVAILABLE",
        "asOf": as_of,
        "assetCount": len(completed),
        "sourceAnalysisIds": source_ids,
        "sourceChecksum": checksum,
        "content": content,
        "generatedAt": max((_timestamp(item) for item in completed), default=None),
    }


class AiAssistantInsightsService:
    """Tenant-scoped view of AI Assistant history for Smart Insights."""

    def __init__(self, memory=None, watchlist_loader=None):
        if memory is None:
            from app.services.analysis_memory import get_analysis_memory
            memory = get_analysis_memory()
        if watchlist_loader is None:
            from app.services.market.watchlist import get_user_watchlist_pairs
            watchlist_loader = get_user_watchlist_pairs
        self.memory = memory
        self.watchlist_loader = watchlist_loader

    def list_dates(self, user_id: int, **_ignored: Any) -> dict[str, Any]:
        watchlist = self.watchlist_loader(user_id)
        reports = self.memory.list_reports_for_user(user_id=user_id)
        wanted = {report_identity(item) for item in watchlist}
        dates = sorted(
            {
                _report_day(item)
                for item in reports
                if report_identity(item) in wanted and _report_day(item)
                and str(item.get("status") or "completed").lower() == "completed"
            },
            reverse=True,
        )
        return {"dates": dates, "source": "AI_ASSISTANT_HISTORY"}

    def get_overview(self, user_id: int, as_of: str | None = None, locale: str = "vi-VN", **_ignored: Any) -> dict[str, Any]:
        watchlist = self.watchlist_loader(user_id)
        reports = self.memory.list_reports_for_user(user_id=user_id)
        dates = self.list_dates(user_id).get("dates") or []
        selected_day = str(as_of or (dates[0] if dates else date.today().isoformat()))[:10]
        selected = select_watchlist_reports_for_date(watchlist, reports, selected_day)
        report_rows = [item for item in selected.values() if item]
        opinions = []
        for item in watchlist:
            key = report_identity(item)
            report = selected.get(key)
            opinions.append({
                "market": item.get("market"),
                "symbol": item.get("symbol"),
                "report": self._public_report(report) if report else None,
                "analysisStatus": "AVAILABLE" if report else "UNAVAILABLE",
            })
        available_count = len(report_rows)
        status = "COMPLETE" if watchlist and available_count == len(opinions) else "PARTIAL" if available_count else "UNAVAILABLE"
        return {
            "asOf": selected_day,
            "status": status,
            "mode": "live",
            "source": "AI_ASSISTANT_HISTORY",
            "opinions": opinions,
            "dailyBrief": build_daily_brief(report_rows, selected_day, locale),
            "summary": {},
            "primary": {},
            "riskAlerts": [],
        }

    @staticmethod
    def _public_report(report: dict[str, Any]) -> dict[str, Any]:
        raw = report.get("full_result") or report.get("raw_result") or {}
        if not isinstance(raw, dict):
            raw = {}
        return {
            "id": report.get("id"),
            "market": report.get("market"),
            "symbol": report.get("symbol"),
            "createdAt": report.get("created_at"),
            "updatedAt": report.get("updated_at"),
            "status": report.get("status") or report.get("task_status") or "completed",
            "decision": report.get("decision") or raw.get("final_decision") or raw.get("trader_decision"),
            "confidence": report.get("confidence"),
            "summary": report.get("summary") or raw.get("summary") or raw.get("reasoning") or raw.get("trader_reasoning"),
            "reasons": report.get("reasons") or raw.get("reasons") or [],
            "scores": report.get("scores") or raw.get("scores") or {},
        }


_service_instance = None


def get_ai_assistant_insights_service() -> AiAssistantInsightsService:
    global _service_instance
    if _service_instance is None:
        _service_instance = AiAssistantInsightsService()
    return _service_instance
