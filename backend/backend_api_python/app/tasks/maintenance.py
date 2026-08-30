"""Periodic maintenance tasks managed by Celery Beat."""

from __future__ import annotations

import os

from app.celery_app import celery_app
from app.runtime.worker_heartbeat import WorkerHeartbeat
from app.utils.db import get_db_connection


def _enabled(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@celery_app.task(name="quantdinger.tasks.worker_heartbeat")
def record_worker_heartbeat() -> None:
    WorkerHeartbeat("celery").record_running()


@celery_app.task(name="quantdinger.tasks.cleanup_runtime_metadata")
def cleanup_runtime_metadata() -> dict:
    retention_days = max(1, int(os.getenv("WORKER_HEARTBEAT_RETENTION_DAYS", "7")))
    with get_db_connection() as db:
        cur = db.cursor()
        cur.execute(
            "DELETE FROM qd_worker_heartbeats WHERE heartbeat_at < NOW() - (%s * INTERVAL '1 day')",
            (retention_days,),
        )
        heartbeats = int(cur.rowcount or 0)
        cur.execute("DELETE FROM qd_process_leases WHERE lease_expires_at < NOW() - INTERVAL '1 day'")
        process_leases = int(cur.rowcount or 0)
        db.commit()
        cur.close()
    return {"heartbeats": heartbeats, "process_leases": process_leases}


@celery_app.task(
    bind=True,
    name="quantdinger.tasks.reflection",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def run_reflection(self):
    del self
    if not _enabled("ENABLE_REFLECTION_WORKER"):
        return {"skipped": True}
    from app.services.reflection import ReflectionService

    return ReflectionService().run_verification_cycle()


@celery_app.task(
    bind=True,
    name="quantdinger.tasks.ai_calibration",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def run_ai_calibration(self):
    del self
    if not _enabled("ENABLE_OFFLINE_AI_CALIBRATION"):
        return {"skipped": True}
    from app.services.ai_calibration import AICalibrationService

    service = AICalibrationService()
    results = []
    markets = os.getenv("AI_CALIBRATION_MARKETS", "Crypto").split(",")
    for market in markets:
        market = market.strip()
        if not market:
            continue
        result = service.calibrate_market(
            market=market,
            lookback_days=int(os.getenv("AI_CALIBRATION_LOOKBACK_DAYS", "30")),
            min_samples=int(os.getenv("AI_CALIBRATION_MIN_SAMPLES", "80")),
        )
        if result is not None:
            results.append(result.__dict__)
    return {"markets": results}


@celery_app.task(
    bind=True,
    name="quantdinger.tasks.market_catalog_sync",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def run_market_catalog_sync(self):
    del self
    if not _enabled("MARKET_CATALOG_AUTO_SYNC"):
        return {"skipped": True}
    from app.services.market_catalog_sync import run_market_catalog_sync_inline

    return run_market_catalog_sync_inline("celery-beat")
