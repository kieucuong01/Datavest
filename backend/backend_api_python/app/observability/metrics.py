"""Prometheus metrics shared by the API process."""

from __future__ import annotations

import os
from pathlib import Path

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)

from app._version import APP_VERSION
from app.runtime.roles import current_process_role
from app.services.smart_insights.operations import get_smart_insights_operations_service
from app.utils.db import get_db_connection


_multiprocess_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR", "").strip()
if _multiprocess_dir:
    Path(_multiprocess_dir).mkdir(parents=True, exist_ok=True)


HTTP_REQUESTS = Counter(
    "quantdinger_http_requests_total",
    "HTTP requests processed by the API.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "quantdinger_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
HTTP_IN_PROGRESS = Gauge(
    "quantdinger_http_requests_in_progress",
    "HTTP requests currently being processed.",
    ("method",),
    multiprocess_mode="livesum",
)
WORKER_HEALTHY = Gauge(
    "quantdinger_workers_healthy",
    "Workers with a fresh heartbeat.",
    ("role",),
    multiprocess_mode="max",
)
WORKER_STALE = Gauge(
    "quantdinger_workers_stale",
    "Workers whose heartbeat is stale.",
    ("role",),
    multiprocess_mode="max",
)
BUILD_INFO = Gauge(
    "quantdinger_build_info",
    "DataVest build and process information.",
    ("version", "role"),
    multiprocess_mode="max",
)
DATAVEST_FEATURE_REQUESTS = Counter(
    "datavest_feature_requests_total",
    "Requests to DataVest feature operations.",
    ("feature", "operation"),
)
DATAVEST_FEATURE_OUTCOMES = Counter(
    "datavest_feature_outcomes_total",
    "Outcomes from DataVest feature operations.",
    ("feature", "operation", "outcome"),
)
SMART_INSIGHTS_SOURCE_FRESHNESS = Gauge(
    "datavest_smart_insights_source_freshness",
    "Current freshness classification for each enabled Smart Insights source.",
    ("source", "market", "status"),
)
SMART_INSIGHTS_SOURCE_LAST_RUN = Gauge(
    "datavest_smart_insights_source_last_run",
    "Latest collector-run status for each enabled Smart Insights source.",
    ("source", "market", "status"),
)
BUILD_INFO.labels(version=APP_VERSION, role=current_process_role().value).set(1)


def _refresh_runtime_metrics() -> None:
    worker_roles = {"scheduler", "celery"}
    worker_counts: dict[str, tuple[int, int]] = {}
    try:
        with get_db_connection() as db:
            cur = db.cursor()
            try:
                cur.execute(
                    """
                    SELECT role,
                           COUNT(*) FILTER (
                               WHERE status = 'running'
                                 AND heartbeat_at >= NOW() - INTERVAL '45 seconds'
                           ) AS healthy,
                           COUNT(*) FILTER (
                               WHERE heartbeat_at < NOW() - INTERVAL '45 seconds'
                           ) AS stale
                    FROM qd_worker_heartbeats
                    GROUP BY role
                    """
                )
                for row in cur.fetchall() or []:
                    role = str(row.get("role") or "unknown")
                    worker_roles.add(role)
                    worker_counts[role] = (
                        int(row.get("healthy") or 0),
                        int(row.get("stale") or 0),
                    )
            finally:
                cur.close()
    except Exception:
        return

    for role in worker_roles:
        healthy, stale = worker_counts.get(role, (0, 0))
        WORKER_HEALTHY.labels(role=role).set(healthy)
        WORKER_STALE.labels(role=role).set(stale)


def _refresh_smart_insights_metrics() -> None:
    try:
        sources = get_smart_insights_operations_service().source_statuses()
    except Exception:
        return

    freshness_states = ("FRESH", "STALE", "UNAVAILABLE")
    run_states = ("SUCCEEDED", "PARTIAL", "FAILED", "QUARANTINED", "QUEUED", "RUNNING", "")
    for source in sources:
        code = str(source.get("code") or "unknown")
        market = str(source.get("market") or "unknown")
        freshness = str(source.get("freshness") or "UNAVAILABLE").upper()
        run_status = str((source.get("lastRun") or {}).get("status") or "").upper()
        for status in freshness_states:
            SMART_INSIGHTS_SOURCE_FRESHNESS.labels(
                source=code, market=market, status=status
            ).set(1 if status == freshness else 0)
        for status in run_states:
            SMART_INSIGHTS_SOURCE_LAST_RUN.labels(
                source=code, market=market, status=status
            ).set(1 if status == run_status else 0)


def render_metrics() -> tuple[bytes, str]:
    _refresh_runtime_metrics()
    _refresh_smart_insights_metrics()
    multiprocess_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR", "").strip()
    if multiprocess_dir:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry), CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST
