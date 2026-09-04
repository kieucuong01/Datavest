"""Smart Insights projections backed only by AI Assistant analysis history.

This module deliberately contains no market scoring, snapshot materialisation or
evidence collector logic.  It presents the analysis that a user has already
asked AI Assistant to produce, pinned to the requested calendar day.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from app.utils.timeutil import VIETNAM_TIME_ZONE, vietnam_calendar_date

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
    return vietnam_calendar_date(report.get("created_at") or report.get("createdAt"))


def _timestamp(report: dict[str, Any]) -> str:
    return str(report.get("created_at") or report.get("createdAt") or "")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso_timestamp(value: Any) -> str | None:
    parsed = _as_datetime(value)
    if parsed is not None:
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    text = str(value or "").strip()
    return text or None


def _public_input_data(raw: dict[str, Any]) -> dict[str, Any]:
    """Return provenance fields that are useful to a user and safe to expose."""
    input_data = _as_dict(raw.get("input_data") or raw.get("inputData"))
    components = input_data.get("components")
    if not isinstance(components, list):
        components = []
    allowed_components = {
        "price", "technical", "macro", "news", "crypto_market_structure",
    }
    safe_components = [
        str(item) for item in components
        if str(item) in allowed_components
    ]
    source = str(input_data.get("price_source") or input_data.get("priceSource") or "").strip()
    source = re.sub(r"[^A-Za-z0-9._-]+", "_", source)[:80] or None
    checksum = str(input_data.get("checksum") or "").strip()
    checksum = checksum[:128] or None
    return {
        "capturedAt": _iso_timestamp(input_data.get("captured_at") or input_data.get("capturedAt")),
        "priceSource": source,
        "timeframe": str(input_data.get("timeframe") or "").strip()[:24] or None,
        "klineAt": _iso_timestamp(input_data.get("kline_at") or input_data.get("klineAt")),
        "checksum": checksum,
        "components": safe_components,
    }


def _default_monitor_loader(user_id: int) -> list[dict[str, Any]]:
    """Load only AI monitor state for the authenticated user's watchlist view."""
    if not user_id:
        return []
    try:
        from app.utils.database import get_db_connection

        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT id, monitor_type, config, is_active, last_run_at, next_run_at,
                       last_result, run_count, updated_at
                FROM qd_position_monitors
                WHERE user_id = ?
                  AND COALESCE(monitor_type, 'ai') = 'ai'
                ORDER BY updated_at DESC, id DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall() or []
            cur.close()
        return [dict(row) for row in rows]
    except Exception:
        return []


def _monitor_public_state(monitor: dict[str, Any], now: datetime) -> dict[str, Any]:
    config = _as_dict(monitor.get("config"))
    last_result = _as_dict(monitor.get("last_result"))
    active = bool(monitor.get("is_active"))
    next_run_at = _as_datetime(monitor.get("next_run_at"))
    if not active:
        state = "PAUSED"
    elif last_result.get("error"):
        state = "FAILED"
    elif next_run_at is not None and next_run_at <= now:
        state = "OVERDUE"
    else:
        state = "SCHEDULED"
    interval = config.get("run_interval_minutes") or config.get("interval_minutes")
    try:
        interval = int(interval) if interval is not None else None
    except (TypeError, ValueError):
        interval = None
    return {
        "id": monitor.get("id"),
        "state": state,
        "isActive": active,
        "lastRunAt": _iso_timestamp(monitor.get("last_run_at")),
        "nextRunAt": _iso_timestamp(monitor.get("next_run_at")),
        "intervalMinutes": interval,
        "runCount": int(monitor.get("run_count") or 0),
        # The monitor error can contain a provider response or an internal
        # exception.  The UI only needs to know that a retry failed, not the
        # untrusted/raw error text.
        "hasError": bool(last_result.get("error")),
    }


def _watchlist_monitor_index(monitors: Iterable[dict[str, Any]], now: datetime) -> dict[str, dict[str, Any]]:
    rank = {"FAILED": 4, "OVERDUE": 3, "SCHEDULED": 2, "PAUSED": 1}
    indexed: dict[str, dict[str, Any]] = {}
    for raw_monitor in monitors:
        config = _as_dict(raw_monitor.get("config"))
        market = canonical_market(config.get("market"))
        symbol = canonical_symbol(config.get("symbol"))
        if not market or not symbol:
            continue
        key = f"{market}:{symbol}"
        current = _monitor_public_state(raw_monitor, now)
        previous = indexed.get(key)
        if previous is None or rank[current["state"]] > rank[previous["state"]]:
            indexed[key] = current
    return indexed


def _report_freshness(report: dict[str, Any] | None, monitor: dict[str, Any], selected_day: str, now: datetime) -> str:
    if not report:
        return "UNAVAILABLE"
    if selected_day != vietnam_calendar_date(now):
        return "HISTORICAL"
    if monitor.get("state") in {"FAILED", "OVERDUE"}:
        return "STALE"
    captured_at = _as_datetime((_public_input_data(report.get("full_result") or report.get("raw_result") or {})).get("capturedAt"))
    if captured_at is None:
        return "UNKNOWN"
    interval = monitor.get("intervalMinutes")
    max_age_minutes = max(30, min(int(interval or 360), 360))
    age_seconds = (now - captured_at).total_seconds()
    return "FRESH" if age_seconds <= max_age_minutes * 60 else "STALE"


def _analysis_status(report: dict[str, Any] | None, freshness: str, monitor: dict[str, Any]) -> str:
    if report:
        return "STALE" if freshness == "STALE" else "HISTORICAL" if freshness == "HISTORICAL" else "AVAILABLE"
    return {
        "PAUSED": "PAUSED",
        "FAILED": "FAILED",
        "OVERDUE": "OVERDUE",
        "SCHEDULED": "PENDING",
    }.get(monitor.get("state"), "UNAVAILABLE")


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

    def __init__(self, memory=None, watchlist_loader=None, monitor_loader=None, now_loader=None):
        if memory is None:
            from app.services.analysis_memory import get_analysis_memory
            memory = get_analysis_memory()
        if watchlist_loader is None:
            from app.services.market.watchlist import get_user_watchlist_pairs
            watchlist_loader = get_user_watchlist_pairs
        if monitor_loader is None:
            monitor_loader = _default_monitor_loader
        self.memory = memory
        self.watchlist_loader = watchlist_loader
        self.monitor_loader = monitor_loader
        self.now_loader = now_loader or (lambda: datetime.now(timezone.utc))

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
        selected_day = str(as_of or (dates[0] if dates else vietnam_calendar_date()))[:10]
        now = self.now_loader()
        if not isinstance(now, datetime):
            now = datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        monitor_index = _watchlist_monitor_index(self.monitor_loader(user_id), now)
        selected = select_watchlist_reports_for_date(watchlist, reports, selected_day)
        report_rows = [item for item in selected.values() if item]
        opinions = []
        for item in watchlist:
            key = report_identity(item)
            report = selected.get(key)
            monitor = monitor_index.get(key, {"state": "MISSING", "isActive": False, "lastRunAt": None, "nextRunAt": None, "intervalMinutes": None, "runCount": 0, "hasError": False})
            freshness = _report_freshness(report, monitor, selected_day, now)
            opinions.append({
                "market": item.get("market"),
                "symbol": item.get("symbol"),
                "report": self._public_report(report) if report else None,
                "monitor": monitor,
                "dataFreshness": freshness,
                "analysisStatus": _analysis_status(report, freshness, monitor),
            })
        available_count = len(report_rows)
        status = "COMPLETE" if watchlist and available_count == len(opinions) else "PARTIAL" if available_count else "UNAVAILABLE"
        return {
            "asOf": selected_day,
            "timeZone": VIETNAM_TIME_ZONE,
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
        detailed_analysis = raw.get("detailed_analysis") or raw.get("analysis") or {}
        if not isinstance(detailed_analysis, dict):
            detailed_analysis = {"technical": str(detailed_analysis)}
        trading_plan = raw.get("trading_plan") or {}
        if not isinstance(trading_plan, dict):
            trading_plan = {}
        market_data = raw.get("market_data") or {}
        if not isinstance(market_data, dict):
            market_data = {}
        crypto_factors = raw.get("crypto_factors") or {}
        if not isinstance(crypto_factors, dict):
            crypto_factors = {}
        consensus = raw.get("consensus") or {}
        if not isinstance(consensus, dict):
            consensus = {}
        trend_outlook = raw.get("trend_outlook") or raw.get("trendOutlook") or {}
        if not isinstance(trend_outlook, dict):
            trend_outlook = {}
        input_data = _public_input_data(raw)
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
            # Keep the existing compact fields above, but expose the safe,
            # read-only detail fields needed to render the same report in Smart
            # Insights. Never pass raw_result, prompts, or provider credentials.
            "model": raw.get("model"),
            "language": raw.get("language"),
            "timeframe": raw.get("timeframe"),
            "detailedAnalysis": detailed_analysis,
            "tradingPlan": trading_plan,
            "risks": report.get("risks") or raw.get("risks") or [],
            "marketData": market_data,
            "inputData": input_data,
            "indicators": raw.get("indicators") if isinstance(raw.get("indicators"), dict) else {},
            "cryptoFactors": crypto_factors,
            "cryptoFactorScore": raw.get("crypto_factor_score"),
            "cryptoFactorBreakdown": raw.get("crypto_factor_breakdown") if isinstance(raw.get("crypto_factor_breakdown"), list) else [],
            "cryptoFactorSummary": raw.get("crypto_factor_summary") or "",
            "objectiveScore": raw.get("objective_score") if isinstance(raw.get("objective_score"), dict) else {},
            "scoreBasedDecision": raw.get("score_based_decision"),
            "consensus": consensus,
            "trendOutlook": trend_outlook,
            "trendOutlookSummary": raw.get("trend_outlook_summary") or raw.get("trendOutlookSummary") or "",
            "analysisTimeMs": raw.get("analysis_time_ms"),
            "llmTimeMs": raw.get("llm_time_ms"),
            "dataCollectionTimeMs": raw.get("data_collection_time_ms"),
        }


_service_instance = None


def get_ai_assistant_insights_service() -> AiAssistantInsightsService:
    global _service_instance
    if _service_instance is None:
        _service_instance = AiAssistantInsightsService()
    return _service_instance
