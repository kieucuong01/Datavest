"""Celery entrypoint for Smart Insights refresh orchestration."""

from __future__ import annotations

import os

from app.celery_app import celery_app


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
        tuple(dict.fromkeys(item.strip().lower() for item in configured.split(",") if item.strip()))
        if configured
        else repository.list_enabled_source_codes()
    )
    if not source_codes:
        return {"skipped": True, "reason": "no_enabled_sources"}
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
    if not normalized:
        return {"skipped": True, "reason": "no_sources"}
    from app.services.smart_insights.repository import SmartInsightsRepository

    repository = SmartInsightsRepository()
    run_id = repository.create_refresh_request(
        requested_by_user_id=None, market="crypto", source_codes=normalized
    )
    run_smart_insights_refresh.delay(run_id)
    return {"queued": True, "runId": run_id, "sourceCount": len(normalized)}


__all__ = ["enqueue_smart_insights_refresh", "enqueue_smart_insights_refresh_for_sources", "run_smart_insights_refresh"]
