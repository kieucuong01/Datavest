"""Operational read model tests for Smart Insights."""

from __future__ import annotations

from datetime import datetime, timezone


def test_operations_snapshot_summarizes_workers_crawl_failures_and_freshness():
    from app.services.smart_insights.operations import SmartInsightsOperationsService

    class Repository:
        def data_health(self):
            return [
                {
                    "code": "fresh-source",
                    "market": "crypto",
                    "enabled": True,
                    "freshness": "FRESH",
                    "lastObservedAt": "2026-09-15T00:00:00+00:00",
                    "lastRun": {"status": "SUCCEEDED"},
                },
                {
                    "code": "failed-source",
                    "market": "crypto",
                    "enabled": True,
                    "freshness": "STALE",
                    "lastObservedAt": "2026-09-12T00:00:00+00:00",
                    "lastRun": {"status": "FAILED", "errorCode": "UPSTREAM_TIMEOUT"},
                },
                {
                    "code": "disabled-source",
                    "market": "crypto",
                    "enabled": False,
                    "freshness": "UNAVAILABLE",
                    "lastRun": {"status": "FAILED"},
                },
            ]

    workers = [
        {
            "role": "celery",
            "healthy": 1,
            "total": 1,
            "stale": 0,
            "lastHeartbeat": datetime(2026, 9, 15, tzinfo=timezone.utc),
        },
        {
            "role": "scheduler",
            "healthy": 0,
            "total": 1,
            "stale": 1,
            "lastHeartbeat": datetime(2026, 9, 15, tzinfo=timezone.utc),
        },
    ]

    service = SmartInsightsOperationsService(
        repository=Repository(),
        worker_health_loader=lambda: workers,
        now=lambda: datetime(2026, 9, 15, tzinfo=timezone.utc),
    )

    snapshot = service.snapshot()

    assert snapshot["summary"] == {
        "workers": {"healthy": 1, "stale": 1, "missing": 0},
        "sources": {
            "enabled": 2,
            "fresh": 1,
            "stale": 1,
            "unavailable": 0,
            "failed": 1,
            "partial": 0,
        },
    }
    assert [row["code"] for row in snapshot["sources"]] == ["failed-source", "fresh-source"]
    assert snapshot["sources"][0]["lastRun"] == {
        "status": "FAILED",
        "errorCode": "UPSTREAM_TIMEOUT",
    }
    assert snapshot["workers"][0]["status"] == "HEALTHY"
    assert snapshot["workers"][1]["status"] == "STALE"


def test_operations_endpoint_requires_an_administrator(monkeypatch):
    from flask import Flask

    from app.routes import smart_insights as routes
    from app.utils import auth

    app = Flask(__name__)
    app.register_blueprint(routes.smart_insights_blp, url_prefix="/api/smart-insights")
    monkeypatch.setattr(
        routes,
        "get_smart_insights_operations_service",
        lambda: type("Operations", (), {"snapshot": lambda _self: {"summary": {}}})(),
    )

    with app.test_client() as client:
        assert client.get("/api/smart-insights/admin/operations").status_code == 401

        monkeypatch.setattr(
            auth,
            "verify_token",
            lambda _token: {"user_id": 7, "_verified_username": "viewer", "_verified_user_role": "viewer"},
        )
        assert client.get(
            "/api/smart-insights/admin/operations",
            headers={"Authorization": "Bearer viewer-token"},
        ).status_code == 403

        monkeypatch.setattr(
            auth,
            "verify_token",
            lambda _token: {"user_id": 1, "_verified_username": "admin", "_verified_user_role": "admin"},
        )
        response = client.get(
            "/api/smart-insights/admin/operations",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.get_json()["data"] == {"summary": {}}
