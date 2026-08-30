"""Application startup hooks and process-local service singletons."""
from __future__ import annotations

import os
from flask import Flask

from app.runtime.roles import ProcessRole, current_process_role
from app.utils.logger import get_logger


logger = get_logger(__name__)

def _is_debug_reloader_parent() -> bool:
    debug = os.getenv("PYTHON_API_DEBUG", "false").lower() == "true"
    return debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true"


def start_portfolio_monitor():
    """Start the portfolio monitor service if enabled."""
    if os.getenv("ENABLE_PORTFOLIO_MONITOR", "true").lower() != "true":
        logger.info("Portfolio monitor is disabled. Set ENABLE_PORTFOLIO_MONITOR=true to enable.")
        return
    if _is_debug_reloader_parent():
        return
    try:
        from app.services.portfolio_monitor import start_monitor_service
        start_monitor_service()
    except Exception as e:
        logger.error(f"Failed to start portfolio monitor: {e}")


def run_startup_hooks(app: Flask) -> None:
    """Start only the services assigned to the current process role."""
    skip_hooks = os.getenv("SKIP_STARTUP_HOOKS", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    if skip_hooks:
        return
    role = current_process_role()
    if role in {ProcessRole.API, ProcessRole.CELERY}:
        logger.info("No process-local background services for role=%s", role.value)
        return
    logger.info("Process services are controlled by the %s entrypoint", role.value)


def _start_scheduler_services(*, include_celery_managed: bool = False) -> None:
    """Start long-lived schedulers that are not Celery tasks."""
    start_portfolio_monitor()
    try:
        from app.services.indicator_signal_alerts import start_indicator_signal_alert_worker

        start_indicator_signal_alert_worker()
    except Exception:
        logger.error("Failed to start indicator signal alert worker", exc_info=True)

    try:
        from app.services.market_catalog_sync import start_market_catalog_sync_on_boot

        start_market_catalog_sync_on_boot()
    except Exception:
        logger.error("Failed to start initial market catalog sync", exc_info=True)

    if not include_celery_managed:
        return
    try:
        from app.services.ai_calibration import start_ai_calibration_worker

        start_ai_calibration_worker()
    except Exception:
        logger.error("Failed to start AI calibration", exc_info=True)
    try:
        from app.services.reflection import start_reflection_worker

        start_reflection_worker()
    except Exception:
        logger.error("Failed to start reflection worker", exc_info=True)
