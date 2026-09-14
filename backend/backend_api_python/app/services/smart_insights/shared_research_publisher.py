"""Worker-only generation for reusable authenticated watchlist research."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Callable, Mapping

from app.services.smart_insights.public_research_publisher import (
    _CONTROL_CHARS,
    _DEEP_MARKET_BY_PUBLIC_MARKET,
    _INTERNAL_RUN_LINE,
    _UPSTREAM_SOURCE_PIN,
    _system_user_id,
)
from app.services.smart_insights.public_reports import PUBLIC_RESEARCH_LOCALE, public_asset_key
from app.services.smart_insights.shared_reports import SharedResearchReportsRepository
from app.utils.logger import get_logger


logger = get_logger(__name__)


class SharedResearchPublisher:
    """Generate only a previously claimed report row from a worker queue."""

    def __init__(
        self,
        *,
        reports: SharedResearchReportsRepository | None = None,
        fast_analysis: Any | None = None,
        trading_repository: Any | None = None,
        enqueue_trading_run: Callable[[str], Any] | None = None,
        fetch_artifact: Callable[..., tuple[bytes, str]] | None = None,
        system_user_id: Callable[[], int] | None = None,
    ) -> None:
        self.reports = reports or SharedResearchReportsRepository()
        self._fast_analysis = fast_analysis
        self._trading_repository = trading_repository
        self._enqueue_trading_run = enqueue_trading_run
        self._fetch_artifact = fetch_artifact
        self._system_user_id = system_user_id or _system_user_id

    def publish_claimed_quick(self, *, asset: Mapping[str, str], period_key: str) -> dict[str, Any]:
        key = public_asset_key(asset)
        try:
            result = self._analysis_service().analyze(
                market=str(asset["market"]), symbol=str(asset["symbol"]),
                language=PUBLIC_RESEARCH_LOCALE, timeframe="1D", user_id=None,
                persist_history=False,
            )
            if result.get("error"):
                raise RuntimeError("analysis_failed")
            self.reports.mark_complete(
                asset_key=key, report_kind="quick", locale=PUBLIC_RESEARCH_LOCALE,
                period_key=period_key, payload=self.quick_payload(str(asset.get("displaySymbol") or asset["symbol"]), result),
            )
            return {"published": True, "assetKey": key}
        except Exception:
            logger.exception("Shared quick report failed for %s", key)
            self.reports.mark_failed(
                asset_key=key, report_kind="quick", locale=PUBLIC_RESEARCH_LOCALE,
                period_key=period_key, failure_code="analysis_failed",
            )
            return {"published": False, "assetKey": key}

    def enqueue_claimed_deep(self, *, asset: Mapping[str, str], period_key: str) -> dict[str, Any]:
        key = public_asset_key(asset)
        run_id = uuid.uuid4().hex
        try:
            request = {
                "market": _DEEP_MARKET_BY_PUBLIC_MARKET[str(asset["market"])],
                "symbol": str(asset["symbol"]), "analysis_date": str(period_key),
                "language": PUBLIC_RESEARCH_LOCALE, "evidence_ref": "shared-watchlist-research",
            }
            config = {"native_config": {"checkpoint_enabled": True}, "selected_analysts": ["market", "social", "news", "fundamentals"]}
            self._trading_agents_repository().create_run(
                user_id=self._system_user_id(), request=request, config=config,
                source_pin=_UPSTREAM_SOURCE_PIN, run_id=run_id,
            )
            self.reports.set_source_run(
                asset_key=key, report_kind="deep", locale=PUBLIC_RESEARCH_LOCALE,
                period_key=period_key, source_run_id=run_id,
            )
            self._trading_enqueue()(run_id)
            return {"queued": True, "assetKey": key}
        except Exception:
            logger.exception("Shared deep report enqueue failed for %s", key)
            self.reports.mark_failed(
                asset_key=key, report_kind="deep", locale=PUBLIC_RESEARCH_LOCALE,
                period_key=period_key, failure_code="enqueue_failed", source_run_id=run_id,
            )
            return {"queued": False, "assetKey": key}

    def sync_pending_deep_reports(self) -> dict[str, int]:
        principal_id = self._system_user_id()
        published = failed = pending = 0
        repository = self._trading_agents_repository()
        fetch = self._artifact_fetcher()
        for report in self.reports.list_pending_deep(locale=PUBLIC_RESEARCH_LOCALE):
            run_id = str(report.get("source_run_id") or "")
            try:
                run = repository.get_run_for_worker(run_id=run_id)
                if not run or int(run.get("user_id") or 0) != principal_id:
                    raise RuntimeError("shared_run_owner_mismatch")
                status = str(run.get("status") or "")
                if status == "succeeded":
                    content, _ = fetch(user_id=principal_id, run_id=run_id, artifact_name="complete_report.md")
                    self.reports.mark_complete(
                        asset_key=report["asset_key"], report_kind="deep", locale=PUBLIC_RESEARCH_LOCALE,
                        period_key=str(report["period_key"]), source_run_id=run_id,
                        payload=self.deep_payload(report_markdown=content.decode("utf-8", errors="replace")),
                    )
                    published += 1
                elif status in {"failed", "cancelled"}:
                    self.reports.mark_failed(
                        asset_key=report["asset_key"], report_kind="deep", locale=PUBLIC_RESEARCH_LOCALE,
                        period_key=str(report["period_key"]), source_run_id=run_id,
                        failure_code=f"trading_agents_{status}",
                    )
                    failed += 1
                else:
                    pending += 1
            except Exception:
                logger.exception("Shared deep report sync failed for %s", report.get("asset_key"))
                self.reports.mark_failed(
                    asset_key=report["asset_key"], report_kind="deep", locale=PUBLIC_RESEARCH_LOCALE,
                    period_key=str(report["period_key"]), source_run_id=run_id, failure_code="sync_failed",
                )
                failed += 1
        return {"published": published, "failed": failed, "pending": pending}

    @staticmethod
    def quick_payload(display_symbol: str, result: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "title": f"Nhận định nhanh {display_symbol}", "summary": str(result.get("summary") or "").strip(),
            "sections": [
                {"title": "Luận điểm", "items": list(result.get("reasons") or [])[:8]},
                {"title": "Rủi ro", "items": list(result.get("risks") or [])[:8]},
            ],
            "decision": str(result.get("decision") or "HOLD").upper(),
            "confidence": result.get("confidence") or (result.get("scores") or {}).get("overall"),
            "provenance": {"engine": "Fast Analysis", "schedule": "on-demand-shared"},
        }

    @staticmethod
    def deep_payload(*, report_markdown: str) -> dict[str, Any]:
        body = _INTERNAL_RUN_LINE.sub("", _CONTROL_CHARS.sub("", str(report_markdown or "")))[:500_000]
        return {"body": body, "provenance": {"engine": "TradingAgents", "schedule": "on-demand-shared"}}

    def _analysis_service(self):
        if self._fast_analysis is None:
            from app.services.fast_analysis import FastAnalysisService
            self._fast_analysis = FastAnalysisService()
        return self._fast_analysis

    def _trading_agents_repository(self):
        if self._trading_repository is None:
            from app.services.trading_agents_repository import TradingAgentsRepository
            self._trading_repository = TradingAgentsRepository()
        return self._trading_repository

    def _trading_enqueue(self):
        if self._enqueue_trading_run is None:
            from app.tasks.trading_agents import enqueue_trading_agents_run
            self._enqueue_trading_run = enqueue_trading_agents_run
        return self._enqueue_trading_run

    def _artifact_fetcher(self):
        if self._fetch_artifact is None:
            from app.tasks.trading_agents import fetch_artifact_from_service
            self._fetch_artifact = fetch_artifact_from_service
        return self._fetch_artifact


__all__ = ["SharedResearchPublisher"]
