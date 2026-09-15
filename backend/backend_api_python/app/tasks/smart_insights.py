"""Celery entrypoint for Smart Insights refresh orchestration."""

from __future__ import annotations

import os
from datetime import date

from app.celery_app import celery_app


_BROWSER_SNAPSHOT_SOURCE_CODES = frozenset({
    "alternative-fng",
    "bitinfocharts-top-addresses",
    "blockchaincenter-altcoin-season",
    "coinshares-weekly",
    "farside-btc-etf",
    "farside-eth-etf",
    "farside-sol-etf",
    "xoomar-btc-etf",
    "xoomar-eth-etf",
    "cryptoetf-btc-etf",
    "cryptoetf-eth-etf",
    "cryptoetf-sol-etf",
    "cryptoetf-xrp-etf",
    "cryptoetf-hyp-etf",
    "cryptoetf-doge-etf",
    "cryptoetf-link-etf",
    "cryptoetf-avax-etf",
    "cryptoetf-hbar-etf",
    "cryptoetf-ltc-etf",
    "cryptoetf-bnb-etf",
    "cryptoetf-dot-etf",
    "cryptoetf-sui-etf",
})


def _bulk_refresh_source_codes(source_codes: tuple[str, ...]) -> tuple[str, ...]:
    """Keep snapshot-owned sources on the crawl-complete import path."""
    return tuple(code for code in source_codes if code not in _BROWSER_SNAPSHOT_SOURCE_CODES)


@celery_app.task(
    bind=True,
    name="datavest.tasks.smart_insights_refresh",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def run_smart_insights_refresh(self, run_id: str) -> dict:
    del self
    from app.services.smart_insights.collectors import execute_refresh

    return execute_refresh(run_id)


@celery_app.task(name="datavest.tasks.enqueue_smart_insights_refresh")
def enqueue_smart_insights_refresh() -> dict:
    if os.getenv("SMART_INSIGHTS_AUTO_REFRESH", "false").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return {"skipped": True, "reason": "disabled"}
    from app.services.smart_insights.repository import SmartInsightsRepository

    repository = SmartInsightsRepository()
    configured = os.getenv("SMART_INSIGHTS_AUTO_REFRESH_SOURCE_CODES", "").strip()
    source_codes = (
        tuple(
            dict.fromkeys(
                item.strip().lower()
                for item in configured.split(",")
                if item.strip() and item.strip().lower() != "cbbi-public"
            )
        )
        if configured
        else repository.list_enabled_source_codes()
    )
    # Bitview has its own daily collection/import, not the broad six-hour job.
    source_codes = tuple(code for code in source_codes if code != "bitview-onchain")
    if not source_codes:
        return {"skipped": True, "reason": "no_enabled_sources"}
    source_codes = _bulk_refresh_source_codes(source_codes)
    if not source_codes:
        return {"skipped": True, "reason": "browser_snapshots_use_callback"}
    run_id = repository.create_refresh_request(
        requested_by_user_id=None,
        market=None,
        source_codes=source_codes,
    )
    run_smart_insights_refresh.delay(run_id)
    return {"queued": True, "runId": run_id, "sourceCount": len(source_codes)}


@celery_app.task(name="datavest.tasks.enqueue_smart_insights_refresh_for_sources")
def enqueue_smart_insights_refresh_for_sources(source_codes: tuple[str, ...]) -> dict:
    """Queue a narrow persisted-snapshot import after the browser worker finishes."""
    normalized = tuple(dict.fromkeys(str(code).strip().lower() for code in source_codes if str(code).strip()))
    normalized = tuple(code for code in normalized if code != "cbbi-public")
    if not normalized:
        return {"skipped": True, "reason": "no_active_sources"}
    from app.services.smart_insights.repository import SmartInsightsRepository

    repository = SmartInsightsRepository()
    run_id = repository.create_refresh_request(
        requested_by_user_id=None, market="crypto", source_codes=normalized
    )
    run_smart_insights_refresh.delay(run_id)
    return {"queued": True, "runId": run_id, "sourceCount": len(normalized)}


@celery_app.task(name="datavest.tasks.enqueue_shared_research_report", acks_late=True)
def enqueue_shared_research_report(*, scope: str, report_kind: str, asset: dict, period_key: str) -> dict:
    """Run one previously claimed reusable report; never iterate every watchlist."""
    from app.services.smart_insights.public_research_publisher import PublicResearchPublisher
    from app.services.smart_insights.shared_research_publisher import SharedResearchPublisher
    from app.services.smart_insights.public_reports import public_asset_key

    key = public_asset_key(asset)
    if report_kind != "deep":
        # A stale queued message must never revive the retired daily Fast
        # Analysis path after deployment.
        return {"skipped": True, "reason": "retired_report_kind", "assetKey": key}
    if scope == "public_common":
        publisher = PublicResearchPublisher()
        return publisher.enqueue_claimed_deep_report(asset_key=key, effective_date=date.fromisoformat(period_key))
    publisher = SharedResearchPublisher()
    return publisher.enqueue_claimed_deep(asset=asset, period_key=period_key)


@celery_app.task(name="datavest.tasks.enqueue_public_deep_reports", acks_late=True)
def enqueue_public_deep_reports() -> dict:
    from app.services.smart_insights.public_research_publisher import PublicResearchPublisher

    return PublicResearchPublisher().enqueue_weekly_deep_reports()


@celery_app.task(name="datavest.tasks.sync_public_deep_reports", acks_late=True)
def sync_public_deep_reports() -> dict:
    from app.services.smart_insights.public_research_publisher import PublicResearchPublisher

    return PublicResearchPublisher().sync_pending_deep_reports()


@celery_app.task(name="datavest.tasks.sync_shared_deep_reports", acks_late=True)
def sync_shared_deep_reports() -> dict:
    from app.services.smart_insights.shared_research_publisher import SharedResearchPublisher

    return SharedResearchPublisher().sync_pending_deep_reports()


__all__ = [
    "enqueue_smart_insights_refresh",
    "enqueue_smart_insights_refresh_for_sources",
    "enqueue_shared_research_report",
    "enqueue_public_deep_reports",
    "sync_public_deep_reports",
    "sync_shared_deep_reports",
    "run_smart_insights_refresh",
]
