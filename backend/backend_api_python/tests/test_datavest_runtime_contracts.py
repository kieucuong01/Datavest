"""DataVest runtime feature-gate and observability contracts."""

from __future__ import annotations

from prometheus_client.parser import text_string_to_metric_families

import app as app_package

from app import create_app
from app.utils import auth as core_auth


SMART_INSIGHTS_PATHS = {
    "/api/smart-insights/overview",
    "/api/smart-insights/dates",
    "/api/smart-insights/evidence/<string:evidence_id>",
    "/api/smart-insights/data-health",
    "/api/smart-insights/refresh",
}
OPTIMIZER_PATHS = {
    "/api/portfolio/optimizer/runs",
    "/api/portfolio/optimizer/runs/<string:run_id>",
    "/api/portfolio/optimizer/runs/<string:run_id>/preview",
    "/api/portfolio/optimizer/runs/<string:run_id>/apply",
}


def _paths(app) -> set[str]:
    return {rule.rule for rule in app.url_map.iter_rules()}


def _authenticate(monkeypatch, *, user_id: int = 7, role: str = "user") -> dict[str, str]:
    monkeypatch.setattr(
        core_auth,
        "verify_token",
        lambda _raw: {
            "sub": "researcher",
            "user_id": user_id,
            "role": role,
            "_verified_username": "researcher",
            "_verified_user_role": role,
        },
    )
    return {"Authorization": "Bearer research-jwt"}


def _feature_samples(metrics_body: str):
    for family in text_string_to_metric_families(metrics_body):
        for sample in family.samples:
            if sample.name.startswith("datavest_feature_"):
                yield sample


def _has_sample(metrics_body: str, name: str, labels: dict[str, str]) -> bool:
    return any(
        sample.name == name and sample.labels == labels and sample.value >= 1
        for sample in _feature_samples(metrics_body)
    )


def test_feature_flags_fail_closed_without_hiding_auth(monkeypatch):
    monkeypatch.setattr(app_package, "_bootstrap_database", lambda: None)
    monkeypatch.delenv("DATAVEST_SMART_INSIGHTS_ENABLED", raising=False)
    monkeypatch.delenv("DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED", raising=False)

    gated_app = create_app("testing")
    paths = _paths(gated_app)

    assert SMART_INSIGHTS_PATHS.isdisjoint(paths)
    assert OPTIMIZER_PATHS.isdisjoint(paths)
    with gated_app.test_client() as gated_client:
        assert gated_client.get("/api/smart-insights/overview").status_code == 404
        assert gated_client.post("/api/portfolio/optimizer/runs", json={}).status_code == 404
        assert gated_client.get("/api/users/profile").status_code == 401


def test_feature_flags_are_enforced_independently(monkeypatch):
    monkeypatch.setattr(app_package, "_bootstrap_database", lambda: None)
    monkeypatch.setenv("DATAVEST_SMART_INSIGHTS_ENABLED", "true")
    monkeypatch.setenv("DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED", "false")
    insights_app = create_app("testing")

    assert SMART_INSIGHTS_PATHS <= _paths(insights_app)
    assert OPTIMIZER_PATHS.isdisjoint(_paths(insights_app))
    with insights_app.test_client() as insights_client:
        assert insights_client.get("/api/smart-insights/overview").status_code == 401
        assert insights_client.post("/api/portfolio/optimizer/runs", json={}).status_code == 404

    monkeypatch.setenv("DATAVEST_SMART_INSIGHTS_ENABLED", "false")
    monkeypatch.setenv("DATAVEST_PORTFOLIO_OPTIMIZER_ENABLED", "true")
    optimizer_app = create_app("testing")

    assert SMART_INSIGHTS_PATHS.isdisjoint(_paths(optimizer_app))
    assert OPTIMIZER_PATHS <= _paths(optimizer_app)
    with optimizer_app.test_client() as optimizer_client:
        assert optimizer_client.get("/api/smart-insights/overview").status_code == 404
        assert optimizer_client.post("/api/portfolio/optimizer/runs", json={}).status_code == 401


def test_smart_insights_metrics_cover_required_operations(client, monkeypatch):
    from app.routes import smart_insights as routes

    class Service:
        def get_overview(self, **_kwargs):
            return {"opinions": []}

        def get_data_health(self, **_kwargs):
            return {"sources": []}

        def queue_refresh(self, **_kwargs):
            return {"status": "QUEUED", "runId": "private-refresh-id"}

    monkeypatch.setattr(routes, "get_smart_insights_service", lambda: Service())

    assert client.get("/api/smart-insights/overview").status_code == 401
    headers = _authenticate(monkeypatch, role="admin")
    assert client.get("/api/smart-insights/overview", headers=headers).status_code == 200
    assert client.get("/api/smart-insights/data-health", headers=headers).status_code == 200
    assert client.post("/api/smart-insights/refresh", headers=headers, json={}).status_code == 202

    body = client.get("/metrics").get_data(as_text=True)
    for operation in ("overview", "data_health", "refresh"):
        base = {"feature": "smart_insights", "operation": operation}
        assert _has_sample(body, "datavest_feature_requests_total", base)
        assert _has_sample(
            body,
            "datavest_feature_outcomes_total",
            {**base, "outcome": "success"},
        )
    assert _has_sample(
        body,
        "datavest_feature_outcomes_total",
        {"feature": "smart_insights", "operation": "overview", "outcome": "client_error"},
    )


def test_optimizer_metrics_cover_create_and_paper_apply_without_dynamic_labels(client, monkeypatch):
    from app.routes import portfolio_optimizer as routes

    class Service:
        def create_run(self, **_kwargs):
            return {"id": "private-run-id", "status": "SUCCEEDED"}

        def apply(self, **_kwargs):
            return {"status": "APPLIED", "executionMode": "SIMULATED"}

    monkeypatch.setattr(routes, "get_portfolio_optimizer_service", lambda: Service())
    headers = _authenticate(monkeypatch)

    assert client.post("/api/portfolio/optimizer/runs", headers=headers, json={}).status_code == 201
    assert client.post(
        "/api/portfolio/optimizer/runs/private-run-id/apply",
        headers=headers,
        json={"planId": "private-plan-id", "idempotencyKey": "private-key"},
    ).status_code == 200

    body = client.get("/metrics").get_data(as_text=True)
    for operation in ("create", "paper_apply"):
        base = {"feature": "portfolio_optimizer", "operation": operation}
        assert _has_sample(body, "datavest_feature_requests_total", base)
        assert _has_sample(
            body,
            "datavest_feature_outcomes_total",
            {**base, "outcome": "success"},
        )

    for sample in _feature_samples(body):
        assert set(sample.labels) <= {"feature", "operation", "outcome"}
        assert "private-run-id" not in sample.labels.values()
        assert "private-plan-id" not in sample.labels.values()
