"""Celery application with lazy Flask application context integration."""

from __future__ import annotations

import os

from celery import Celery, Task
from celery.schedules import crontab
from app.config.redis_urls import celery_broker_url, celery_result_backend_url


_CRYPTO_ETF_DAILY_SOURCES = (
    (
        "cryptoetf-btc-etf", "cryptoetf-eth-etf", "cryptoetf-sol-etf",
        "cryptoetf-xrp-etf", "cryptoetf-hyp-etf", "cryptoetf-doge-etf",
        "cryptoetf-link-etf", "cryptoetf-avax-etf", "cryptoetf-hbar-etf",
        "cryptoetf-ltc-etf", "cryptoetf-bnb-etf", "cryptoetf-dot-etf",
        "cryptoetf-sui-etf",
    )
    if os.getenv("CRYPTOETF_API_KEY", "").strip()
    else ("xoomar-btc-etf", "xoomar-eth-etf", "farside-sol-etf")
)
_CRYPTO_DERIVATIVES_DAILY_SOURCES = ("bybit-derivatives", "binance-usdm-derivatives", "deribit-public-derivatives")


class FlaskContextTask(Task):
    abstract = True
    _flask_app = None

    def __call__(self, *args, **kwargs):
        if self._flask_app is None:
            os.environ["QD_PROCESS_ROLE"] = "celery"
            from app import create_app

            self._flask_app = create_app(register_http_routes=False)
        with self._flask_app.app_context():
            return self.run(*args, **kwargs)


celery_app = Celery("quantdinger", task_cls=FlaskContextTask)
celery_app.conf.update(
    broker_url=celery_broker_url(),
    result_backend=celery_result_backend_url(),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=os.getenv("TZ", "Asia/Shanghai"),
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=max(1, int(os.getenv("CELERY_WORKER_PREFETCH", "1"))),
    worker_max_tasks_per_child=max(1, int(os.getenv("CELERY_MAX_TASKS_PER_CHILD", "100"))),
    task_soft_time_limit=max(60, int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "3300"))),
    task_time_limit=max(120, int(os.getenv("CELERY_TASK_TIME_LIMIT", "3600"))),
    result_expires=max(3600, int(os.getenv("CELERY_RESULT_EXPIRES", "86400"))),
    broker_transport_options={
        "visibility_timeout": max(3600, int(os.getenv("CELERY_VISIBILITY_TIMEOUT", "7200"))),
    },
    imports=(
        "app.tasks.agent_jobs",
        "app.tasks.fast_analysis",
        "app.tasks.maintenance",
        "app.tasks.smart_insights",
    ),
    task_routes={
        "quantdinger.tasks.fast_analysis": {"queue": "ai"},
        "quantdinger.tasks.agent_job": {"queue": "jobs"},
        "quantdinger.tasks.reflection": {"queue": "maintenance"},
        "quantdinger.tasks.ai_calibration": {"queue": "maintenance"},
        "quantdinger.tasks.market_catalog_sync": {"queue": "maintenance"},
        "quantdinger.tasks.worker_heartbeat": {"queue": "maintenance"},
        "quantdinger.tasks.cleanup_runtime_metadata": {"queue": "maintenance"},
        "datavest.tasks.smart_insights_refresh": {"queue": "maintenance"},
        "datavest.tasks.enqueue_smart_insights_refresh": {"queue": "maintenance"},
        "datavest.tasks.enqueue_smart_insights_refresh_for_sources": {"queue": "maintenance"},
    },
    beat_schedule={
        "reflection-cycle": {
            "task": "quantdinger.tasks.reflection",
            "schedule": max(300, int(os.getenv("REFLECTION_WORKER_INTERVAL_SEC", "86400"))),
        },
        "ai-calibration-cycle": {
            "task": "quantdinger.tasks.ai_calibration",
            "schedule": max(3600, int(os.getenv("AI_CALIBRATION_INTERVAL_SEC", "86400"))),
        },
        "market-catalog-sync": {
            "task": "quantdinger.tasks.market_catalog_sync",
            "schedule": max(900, int(os.getenv("MARKET_CATALOG_SYNC_INTERVAL_SEC", "86400"))),
        },
        "celery-worker-heartbeat": {
            "task": "quantdinger.tasks.worker_heartbeat",
            "schedule": 10.0,
        },
        "runtime-metadata-cleanup": {
            "task": "quantdinger.tasks.cleanup_runtime_metadata",
            "schedule": 86400.0,
        },
        "smart-insights-refresh": {
            "task": "datavest.tasks.enqueue_smart_insights_refresh",
            "schedule": max(900, int(os.getenv("SMART_INSIGHTS_REFRESH_INTERVAL_SEC", "21600"))),
        },
        "crypto-insights-daily-import": {
            "task": "datavest.tasks.enqueue_smart_insights_refresh_for_sources",
            "schedule": crontab(hour=9, minute=15),
            "args": (("alternative-fng", *_CRYPTO_ETF_DAILY_SOURCES, "blockchaincenter-altcoin-season", "cbbi-public", "bitinfocharts-top-addresses", "coinmetrics-community"),),
        },
        "crypto-derivatives-daily-import": {
            "task": "datavest.tasks.enqueue_smart_insights_refresh_for_sources",
            "schedule": crontab(hour=0, minute=40),
            "args": (_CRYPTO_DERIVATIVES_DAILY_SOURCES,),
        },
        "crypto-derivatives-daily-retry": {
            "task": "datavest.tasks.enqueue_smart_insights_refresh_for_sources",
            "schedule": crontab(hour=2, minute=15),
            "args": (_CRYPTO_DERIVATIVES_DAILY_SOURCES,),
        },
        "crypto-insights-coinshares-import-mon": {
            "task": "datavest.tasks.enqueue_smart_insights_refresh_for_sources",
            "schedule": crontab(day_of_week="mon", hour=18, minute=15),
            "args": (("coinshares-weekly",),),
        },
        "crypto-insights-coinshares-import-tue": {
            "task": "datavest.tasks.enqueue_smart_insights_refresh_for_sources",
            "schedule": crontab(day_of_week="tue", hour=18, minute=15),
            "args": (("coinshares-weekly",),),
        },
    },
)

__all__ = ["celery_app"]
