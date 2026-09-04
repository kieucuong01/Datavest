"""Celery routing and durable task boundary tests."""

from __future__ import annotations


def test_celery_queues_keep_trading_outside_task_system():
    from app.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert routes["quantdinger.tasks.agent_job"]["queue"] == "jobs"
    assert routes["quantdinger.tasks.fast_analysis"]["queue"] == "ai"
    assert "strategy" not in " ".join(routes).lower()


def test_celery_beat_owns_periodic_maintenance():
    from app.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert schedule["reflection-cycle"]["task"] == "quantdinger.tasks.reflection"
    assert schedule["ai-calibration-cycle"]["task"] == "quantdinger.tasks.ai_calibration"
    assert schedule["market-catalog-sync"]["task"] == "quantdinger.tasks.market_catalog_sync"
    assert schedule["market-catalog-sync"]["schedule"] == 86400
    assert schedule["smart-insights-refresh"]["task"] == "datavest.tasks.enqueue_smart_insights_refresh"
    assert schedule["smart-insights-refresh"]["schedule"] == 21600
    assert schedule["crypto-insights-daily-import"]["task"] == "datavest.tasks.enqueue_smart_insights_refresh_for_sources"
    assert schedule["crypto-insights-daily-import-retry"]["task"] == "datavest.tasks.enqueue_smart_insights_refresh_for_sources"
    assert schedule["crypto-derivatives-daily-import"]["task"] == "datavest.tasks.enqueue_smart_insights_refresh_for_sources"
    assert schedule["crypto-derivatives-daily-retry"]["task"] == "datavest.tasks.enqueue_smart_insights_refresh_for_sources"


def test_celery_beat_defaults_to_vietnam_timezone_for_crypto_snapshot_handoff():
    """A missing server TZ must not shift the importer into the crawler window."""
    from app.celery_app import celery_app

    assert celery_app.conf.timezone == "Asia/Ho_Chi_Minh"


def test_celery_beat_runs_watchlist_ai_analysis_at_7am_vietnam_time():
    """Every watched asset receives the system daily analysis independently of user schedules."""
    from app.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule["daily-watchlist-ai-analysis"]

    assert schedule["task"] == "datavest.tasks.run_daily_watchlist_ai_analysis"
    assert schedule["schedule"].hour == {7}
    assert schedule["schedule"].minute == {0}


def test_fast_analysis_dispatches_to_celery(monkeypatch):
    from app.services import fast_analysis_tasks
    from app.tasks.fast_analysis import execute_fast_analysis

    calls = []
    monkeypatch.setenv("CELERY_TASKS_ENABLED", "true")
    monkeypatch.setattr(execute_fast_analysis, "delay", lambda *args, **kwargs: calls.append((args, kwargs)))

    fast_analysis_tasks.start_async_analysis_task(1, "Crypto", "BTC/USDT")

    assert calls == [((1, "Crypto", "BTC/USDT"), {})]
