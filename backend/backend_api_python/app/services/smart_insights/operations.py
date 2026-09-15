"""Private operational read model for Smart Insights collectors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from app.services.smart_insights.repository import SmartInsightsRepository
from app.utils.db import get_db_connection


_RUN_STATUSES = ("SUCCEEDED", "PARTIAL", "FAILED", "QUARANTINED", "QUEUED", "RUNNING")
_FRESHNESS_STATES = ("FRESH", "STALE", "UNAVAILABLE")


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


class SmartInsightsOperationsService:
    """Summarise worker and source state without reading host journals."""

    def __init__(
        self,
        *,
        repository: SmartInsightsRepository | None = None,
        worker_health_loader: Callable[[], list[dict[str, Any]]] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository or SmartInsightsRepository()
        self._worker_health_loader = worker_health_loader or self._load_worker_health
        self._now = now or (lambda: datetime.now(timezone.utc))

    def snapshot(self) -> dict[str, Any]:
        workers = self._workers()
        sources = self.source_statuses()
        return {
            "generatedAt": _iso(self._now()),
            "summary": {
                "workers": {
                    "healthy": sum(1 for row in workers if row["status"] == "HEALTHY"),
                    "stale": sum(1 for row in workers if row["status"] == "STALE"),
                    "missing": sum(1 for row in workers if row["status"] == "MISSING"),
                },
                "sources": {
                    "enabled": len(sources),
                    "fresh": sum(1 for row in sources if row["freshness"] == "FRESH"),
                    "stale": sum(1 for row in sources if row["freshness"] == "STALE"),
                    "unavailable": sum(
                        1 for row in sources if row["freshness"] == "UNAVAILABLE"
                    ),
                    "failed": sum(
                        1
                        for row in sources
                        if row["lastRun"].get("status") in {"FAILED", "QUARANTINED"}
                    ),
                    "partial": sum(
                        1 for row in sources if row["lastRun"].get("status") == "PARTIAL"
                    ),
                },
            },
            "workers": workers,
            "sources": sources,
        }

    def source_statuses(self) -> list[dict[str, Any]]:
        """Return enabled-source status for metrics without querying worker state."""
        return self._sources()

    def _workers(self) -> list[dict[str, Any]]:
        rows = self._worker_health_loader()
        normalized = []
        for row in rows:
            healthy = int(row.get("healthy") or 0)
            total = int(row.get("total") or 0)
            stale = int(row.get("stale") or 0)
            status = "HEALTHY" if healthy else "STALE" if total or stale else "MISSING"
            normalized.append(
                {
                    "role": str(row.get("role") or "unknown"),
                    "healthy": healthy,
                    "total": total,
                    "stale": stale,
                    "lastHeartbeat": _iso(row.get("lastHeartbeat")),
                    "status": status,
                }
            )
        return sorted(normalized, key=lambda row: row["role"])

    def _sources(self) -> list[dict[str, Any]]:
        rows = self.repository.data_health()
        normalized = []
        for row in rows:
            if not bool(row.get("enabled")):
                continue
            freshness = str(row.get("freshness") or "UNAVAILABLE").upper()
            if freshness not in _FRESHNESS_STATES:
                freshness = "UNAVAILABLE"
            last_run = row.get("lastRun")
            last_run = last_run if isinstance(last_run, Mapping) else {}
            run_status = str(last_run.get("status") or "").upper()
            normalized.append(
                {
                    "code": str(row.get("code") or "unknown"),
                    "market": str(row.get("market") or "unknown"),
                    "freshness": freshness,
                    "lastObservedAt": row.get("lastObservedAt"),
                    "lastRun": {
                        "status": run_status if run_status in _RUN_STATUSES else "",
                        "errorCode": str(last_run.get("errorCode") or "") or None,
                    },
                }
            )
        return sorted(normalized, key=lambda row: (row["market"], row["code"]))

    @staticmethod
    def _load_worker_health() -> list[dict[str, Any]]:
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
                           COUNT(*) FILTER (WHERE status = 'running') AS total,
                           COUNT(*) FILTER (
                               WHERE status = 'running'
                                 AND heartbeat_at < NOW() - INTERVAL '45 seconds'
                           ) AS stale,
                           MAX(heartbeat_at) AS last_heartbeat
                    FROM qd_worker_heartbeats
                    GROUP BY role
                    """
                )
                return [
                    {
                        "role": row.get("role"),
                        "healthy": row.get("healthy"),
                        "total": row.get("total"),
                        "stale": row.get("stale"),
                        "lastHeartbeat": row.get("last_heartbeat"),
                    }
                    for row in cur.fetchall() or []
                ]
            finally:
                cur.close()


def get_smart_insights_operations_service() -> SmartInsightsOperationsService:
    return SmartInsightsOperationsService()


__all__ = ["SmartInsightsOperationsService", "get_smart_insights_operations_service"]
