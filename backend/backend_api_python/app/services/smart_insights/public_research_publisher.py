"""Scheduled, tenant-free publication of the fixed guest research set."""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any, Callable, Mapping

from app.services.smart_insights.public_reports import (
    PUBLIC_RESEARCH_ASSET_SCOPE,
    PUBLIC_RESEARCH_LOCALE,
    PublicResearchReportsRepository,
    public_asset_key,
)
from app.utils.db import get_db_connection
from app.utils.logger import get_logger


logger = get_logger(__name__)
PUBLIC_RESEARCH_SYSTEM_USERNAME = "__datavest_public_research__"
_UPSTREAM_SOURCE_PIN = "TauricResearch/TradingAgents@9dee508c44662702281a8dbaad1f7b42179b5ba7"
_DEEP_MARKET_BY_PUBLIC_MARKET = {"Crypto": "Crypto", "VNStock": "VNStock", "Forex": "Gold"}
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INTERNAL_RUN_LINE = re.compile(r"(?im)^.*\b(?:run[ _-]?id|internal-run)\b.*(?:\r?\n|$)")


def _effective_date(value: date | None = None) -> date:
    return value or date.today()


def _system_user_id() -> int:
    with get_db_connection() as db:
        cur = db.cursor()
        try:
            cur.execute(
                "SELECT id FROM qd_users WHERE username = ? AND status = 'disabled' LIMIT 1",
                (PUBLIC_RESEARCH_SYSTEM_USERNAME,),
            )
            row = cur.fetchone()
        finally:
            cur.close()
    if not row:
        raise RuntimeError("public_research_system_principal_missing")
    return int(dict(row)["id"])


class PublicResearchPublisher:
    """Projects system-owned runs into a bounded public report surface."""

    def __init__(
        self,
        *,
        reports: PublicResearchReportsRepository | None = None,
        fast_analysis: Any | None = None,
        trading_repository: Any | None = None,
        enqueue_trading_run: Callable[[str], Any] | None = None,
        fetch_artifact: Callable[..., tuple[bytes, str]] | None = None,
        system_user_id: Callable[[], int] | None = None,
    ) -> None:
        self.reports = reports or PublicResearchReportsRepository()
        self._fast_analysis = fast_analysis
        self._trading_repository = trading_repository
        self._enqueue_trading_run = enqueue_trading_run
        self._fetch_artifact = fetch_artifact
        self._system_user_id = system_user_id or _system_user_id

    def publish_daily_quick_reports(self, *, effective_date: date | None = None) -> dict[str, int]:
        run_date = _effective_date(effective_date)
        published = failed = 0
        analysis = self._analysis_service()
        for asset in PUBLIC_RESEARCH_ASSET_SCOPE:
            key = public_asset_key(asset)
            self.reports.mark_pending(
                asset_key=key,
                report_kind="quick",
                locale=PUBLIC_RESEARCH_LOCALE,
                effective_date=run_date,
            )
            try:
                result = analysis.analyze(
                    market=asset["market"],
                    symbol=asset["symbol"],
                    language=PUBLIC_RESEARCH_LOCALE,
                    timeframe="1D",
                    user_id=None,
                    persist_history=False,
                )
                if result.get("error"):
                    raise RuntimeError("analysis_failed")
                self.reports.mark_complete(
                    asset_key=key,
                    report_kind="quick",
                    locale=PUBLIC_RESEARCH_LOCALE,
                    effective_date=run_date,
                    payload=self._quick_payload(asset["displaySymbol"], result),
                )
                published += 1
            except Exception:
                logger.exception("Public quick report failed for %s", key)
                self.reports.mark_failed(
                    asset_key=key,
                    report_kind="quick",
                    locale=PUBLIC_RESEARCH_LOCALE,
                    effective_date=run_date,
                    failure_code="analysis_failed",
                )
                failed += 1
        return {"published": published, "failed": failed}

    def enqueue_weekly_deep_reports(self, *, effective_date: date | None = None) -> dict[str, int]:
        return self._enqueue_deep_reports(
            assets=PUBLIC_RESEARCH_ASSET_SCOPE,
            effective_date=effective_date,
        )

    def enqueue_initial_deep_reports(
        self,
        *,
        asset_keys: tuple[str, ...],
        effective_date: date | None = None,
    ) -> dict[str, int]:
        """Queue the first public deep run for an explicit, bounded asset set."""
        requested = {str(asset_key or "").strip() for asset_key in asset_keys}
        assets = tuple(
            asset for asset in PUBLIC_RESEARCH_ASSET_SCOPE
            if public_asset_key(asset) in requested
        )
        return self._enqueue_deep_reports(assets=assets, effective_date=effective_date)

    def publish_claimed_quick_report(self, *, asset_key: str, effective_date: date | None = None) -> dict[str, Any]:
        """Finish a public quick report whose period was atomically claimed by an API request."""
        asset = self._asset_for_key(asset_key)
        run_date = _effective_date(effective_date)
        try:
            result = self._analysis_service().analyze(
                market=asset["market"], symbol=asset["symbol"], language=PUBLIC_RESEARCH_LOCALE,
                timeframe="1D", user_id=None, persist_history=False,
            )
            if result.get("error"):
                raise RuntimeError("analysis_failed")
            self.reports.mark_complete(
                asset_key=asset_key, report_kind="quick", locale=PUBLIC_RESEARCH_LOCALE,
                effective_date=run_date, payload=self._quick_payload(asset["displaySymbol"], result),
            )
            return {"published": True, "assetKey": asset_key}
        except Exception:
            logger.exception("Public quick report failed for %s", asset_key)
            self.reports.mark_failed(
                asset_key=asset_key, report_kind="quick", locale=PUBLIC_RESEARCH_LOCALE,
                effective_date=run_date, failure_code="analysis_failed",
            )
            return {"published": False, "assetKey": asset_key}

    def enqueue_claimed_deep_report(self, *, asset_key: str, effective_date: date | None = None) -> dict[str, Any]:
        """Create one system-owned deep run after an API request claimed its period."""
        asset = self._asset_for_key(asset_key)
        run_date = _effective_date(effective_date)
        run_id = uuid.uuid4().hex
        try:
            request = {
                "market": _DEEP_MARKET_BY_PUBLIC_MARKET[asset["market"]],
                "symbol": asset["symbol"], "analysis_date": run_date.isoformat(),
                "language": PUBLIC_RESEARCH_LOCALE, "evidence_ref": "public-guest-research",
            }
            config = {"native_config": {"checkpoint_enabled": True}, "selected_analysts": ["market", "social", "news", "fundamentals"]}
            self._trading_agents_repository().create_run(
                user_id=self._system_user_id(), request=request, config=config,
                source_pin=_UPSTREAM_SOURCE_PIN, run_id=run_id,
            )
            self.reports.mark_pending(
                asset_key=asset_key, report_kind="deep", locale=PUBLIC_RESEARCH_LOCALE,
                effective_date=run_date, source_run_id=run_id,
            )
            self._trading_enqueue()(run_id)
            return {"queued": True, "assetKey": asset_key}
        except Exception:
            logger.exception("Public deep report enqueue failed for %s", asset_key)
            self.reports.mark_failed(
                asset_key=asset_key, report_kind="deep", locale=PUBLIC_RESEARCH_LOCALE,
                effective_date=run_date, failure_code="enqueue_failed", source_run_id=run_id,
            )
            return {"queued": False, "assetKey": asset_key}

    def _enqueue_deep_reports(
        self,
        *,
        assets: tuple[Mapping[str, str], ...],
        effective_date: date | None = None,
    ) -> dict[str, int]:
        run_date = _effective_date(effective_date)
        principal_id = self._system_user_id()
        repository = self._trading_agents_repository()
        enqueue = self._trading_enqueue()
        queued = failed = 0
        for asset in assets:
            key = public_asset_key(asset)
            run_id = uuid.uuid4().hex
            try:
                request = {
                    "market": _DEEP_MARKET_BY_PUBLIC_MARKET[asset["market"]],
                    "symbol": asset["symbol"],
                    "analysis_date": run_date.isoformat(),
                    "language": PUBLIC_RESEARCH_LOCALE,
                    "evidence_ref": "public-guest-research",
                }
                config = {
                    "native_config": {"checkpoint_enabled": True},
                    "selected_analysts": ["market", "social", "news", "fundamentals"],
                }
                repository.create_run(
                    user_id=principal_id,
                    request=request,
                    config=config,
                    source_pin=_UPSTREAM_SOURCE_PIN,
                    run_id=run_id,
                )
                self.reports.mark_pending(
                    asset_key=key,
                    report_kind="deep",
                    locale=PUBLIC_RESEARCH_LOCALE,
                    effective_date=run_date,
                    source_run_id=run_id,
                )
                enqueue(run_id)
                queued += 1
            except Exception:
                logger.exception("Public deep report enqueue failed for %s", key)
                self.reports.mark_failed(
                    asset_key=key,
                    report_kind="deep",
                    locale=PUBLIC_RESEARCH_LOCALE,
                    effective_date=run_date,
                    failure_code="enqueue_failed",
                    source_run_id=run_id,
                )
                failed += 1
        return {"queued": queued, "failed": failed}

    def sync_pending_deep_reports(self) -> dict[str, int]:
        principal_id = self._system_user_id()
        repository = self._trading_agents_repository()
        fetch = self._artifact_fetcher()
        published = failed = pending = 0
        for report in self.reports.list_pending_deep(locale=PUBLIC_RESEARCH_LOCALE):
            run_id = str(report.get("source_run_id") or "")
            try:
                run = repository.get_run_for_worker(run_id=run_id)
                if not run or int(run.get("user_id") or 0) != principal_id:
                    raise RuntimeError("public_run_owner_mismatch")
                status = str(run.get("status") or "")
                if status == "succeeded":
                    content, _content_type = fetch(
                        user_id=principal_id,
                        run_id=run_id,
                        artifact_name="complete_report.md",
                    )
                    asset = next(item for item in PUBLIC_RESEARCH_ASSET_SCOPE if public_asset_key(item) == report["asset_key"])
                    self.reports.mark_complete(
                        asset_key=report["asset_key"],
                        report_kind="deep",
                        locale=PUBLIC_RESEARCH_LOCALE,
                        effective_date=report["effective_date"],
                        source_run_id=run_id,
                        payload=self.build_deep_payload(
                            display_symbol=asset["displaySymbol"],
                            report_markdown=content.decode("utf-8", errors="replace"),
                        ),
                    )
                    published += 1
                elif status in {"failed", "cancelled"}:
                    self.reports.mark_failed(
                        asset_key=report["asset_key"],
                        report_kind="deep",
                        locale=PUBLIC_RESEARCH_LOCALE,
                        effective_date=report["effective_date"],
                        source_run_id=run_id,
                        failure_code=f"trading_agents_{status}",
                    )
                    failed += 1
                else:
                    pending += 1
            except Exception:
                logger.exception("Public deep report sync failed for %s", report.get("asset_key"))
                self.reports.mark_failed(
                    asset_key=report["asset_key"],
                    report_kind="deep",
                    locale=PUBLIC_RESEARCH_LOCALE,
                    effective_date=report["effective_date"],
                    source_run_id=run_id,
                    failure_code="sync_failed",
                )
                failed += 1
        return {"published": published, "failed": failed, "pending": pending}

    @staticmethod
    def _quick_payload(display_symbol: str, result: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "title": f"Nhận định nhanh {display_symbol}",
            "summary": str(result.get("summary") or "").strip(),
            "sections": [
                {"title": "Luận điểm", "items": list(result.get("reasons") or [])[:8]},
                {"title": "Rủi ro", "items": list(result.get("risks") or [])[:8]},
            ],
            "decision": str(result.get("decision") or "HOLD").upper(),
            "confidence": result.get("confidence") or (result.get("scores") or {}).get("overall"),
            "provenance": {"engine": "Fast Analysis", "schedule": "daily"},
        }

    @staticmethod
    def build_deep_payload(*, display_symbol: str, report_markdown: str) -> dict[str, Any]:
        body = _CONTROL_CHARS.sub("", str(report_markdown or ""))[:500_000]
        body = _INTERNAL_RUN_LINE.sub("", body)
        return {
            "title": f"Phân tích chuyên sâu {display_symbol}",
            "body": body,
            "provenance": {"engine": "TradingAgents", "schedule": "weekly"},
        }

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

    @staticmethod
    def _asset_for_key(asset_key: str) -> Mapping[str, str]:
        key = str(asset_key or "").strip()
        asset = next((item for item in PUBLIC_RESEARCH_ASSET_SCOPE if public_asset_key(item) == key), None)
        if asset is None:
            raise ValueError("unsupported_public_asset")
        return asset


__all__ = ["PUBLIC_RESEARCH_SYSTEM_USERNAME", "PublicResearchPublisher"]
