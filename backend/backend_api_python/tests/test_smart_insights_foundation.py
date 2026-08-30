"""Smart Insights foundation contracts for the QuantDinger-first backend."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.utils import auth as core_auth


BACKEND_ROOT = Path(__file__).resolve().parents[1]


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


def test_additive_migration_defines_required_provenance_tables_and_live_demo_gate():
    migration = (
        BACKEND_ROOT / "migrations" / "20260824_smart_insights_foundation.sql"
    ).read_text(encoding="utf-8")

    for table in (
        "data_sources",
        "collector_runs",
        "observations",
        "insight_snapshots",
        "asset_opinions",
        "insight_evidence_links",
        "user_insight_preferences",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration

    assert "CHECK (data_class IN ('LIVE', 'DEMO'))" in migration
    assert "UNIQUE (data_source_id, checksum)" in migration
    assert "REFERENCES qd_users(id)" in migration
    assert "organization_id" not in migration


def test_observation_contract_has_stable_checksum_and_complete_provenance():
    from app.services.smart_insights.contracts import DataClass, Observation

    observed_at = datetime(2026, 8, 24, 2, 0, tzinfo=timezone.utc)
    row = Observation.create(
        source_code="fred",
        source_url="https://fred.stlouisfed.org/series/CPIAUCSL",
        market="macro",
        effective_at=observed_at,
        observed_at=observed_at,
        methodology_version="fred-cpi-v1",
        value={"metric": "macro.cpi", "value": "2.7", "unit": "percent"},
        warnings=("revised",),
        data_class=DataClass.LIVE,
    )
    equivalent = Observation.create(
        source_code="fred",
        source_url="https://fred.stlouisfed.org/series/CPIAUCSL",
        market="macro",
        effective_at=observed_at,
        observed_at=observed_at,
        methodology_version="fred-cpi-v1",
        value={"unit": "percent", "value": "2.7", "metric": "macro.cpi"},
        warnings=("revised",),
        data_class="LIVE",
    )

    assert row.checksum == equivalent.checksum
    assert len(row.checksum) == 64
    assert row.provenance()["dataClass"] == "LIVE"
    assert row.provenance()["warnings"] == ["revised"]

    with pytest.raises(ValueError, match="HTTPS"):
        Observation.create(
            source_code="bad",
            source_url="http://example.test/data?api_key=secret",
            market="macro",
            effective_at=observed_at,
            observed_at=observed_at,
            methodology_version="v1",
            value={"metric": "macro.bad", "value": 1},
            data_class="LIVE",
        )


def test_production_evidence_gate_rejects_demo_and_missing_provenance():
    from app.services.smart_insights.contracts import EvidencePolicyError
    from app.services.smart_insights.evidence import require_live_evidence

    base = {
        "id": "obs-1",
        "dataClass": "LIVE",
        "source": "fred",
        "sourceUrl": "https://fred.stlouisfed.org/series/CPIAUCSL",
        "observedAt": "2026-08-24T02:00:00+00:00",
        "effectiveAt": "2026-08-24T02:00:00+00:00",
        "methodologyVersion": "fred-cpi-v1",
        "checksum": "a" * 64,
    }
    assert require_live_evidence([base]) == (base,)

    with pytest.raises(EvidencePolicyError, match="DEMO_EVIDENCE_FORBIDDEN"):
        require_live_evidence([{**base, "dataClass": "DEMO"}])
    with pytest.raises(EvidencePolicyError, match="INCOMPLETE_PROVENANCE"):
        require_live_evidence([{key: value for key, value in base.items() if key != "checksum"}])


def test_smart_insights_routes_are_registered_and_require_jwt(app, client):
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/smart-insights/overview",
        "/api/smart-insights/dates",
        "/api/smart-insights/evidence/<string:evidence_id>",
        "/api/smart-insights/data-health",
        "/api/smart-insights/refresh",
    } <= paths

    for method, path in (
        ("GET", "/api/smart-insights/overview"),
        ("GET", "/api/smart-insights/dates"),
        ("GET", "/api/smart-insights/evidence/obs-1"),
        ("GET", "/api/smart-insights/data-health"),
        ("POST", "/api/smart-insights/refresh"),
    ):
        response = client.open(path, method=method, json={})
        assert response.status_code == 401, (method, path)


def test_overview_passes_user_scope_and_explicit_mode(client, monkeypatch):
    from app.routes import smart_insights as routes

    captured = {}

    class Service:
        def get_overview(self, *, user_id, as_of, market, mode):
            captured.update(user_id=user_id, as_of=as_of, market=market, mode=mode)
            return {"asOf": as_of, "market": market, "mode": mode, "opinions": []}

    monkeypatch.setattr(routes, "get_smart_insights_service", lambda: Service())
    response = client.get(
        "/api/smart-insights/overview?as_of=2026-08-24&market=crypto&mode=demo",
        headers=_authenticate(monkeypatch, user_id=19),
    )

    assert response.status_code == 200
    assert captured == {
        "user_id": 19,
        "as_of": "2026-08-24",
        "market": "crypto",
        "mode": "demo",
    }
    assert response.get_json()["data"]["mode"] == "demo"


def test_refresh_is_admin_only_and_queues_audited_request(client, monkeypatch):
    from app.routes import smart_insights as routes

    class Service:
        def __init__(self):
            self.calls = []

        def queue_refresh(self, *, requested_by_user_id, market, source_codes):
            self.calls.append((requested_by_user_id, market, source_codes))
            return {"status": "QUEUED", "runId": "run-1"}

    service = Service()
    monkeypatch.setattr(routes, "get_smart_insights_service", lambda: service)

    forbidden = client.post(
        "/api/smart-insights/refresh",
        headers=_authenticate(monkeypatch, role="user"),
        json={"market": "macro"},
    )
    assert forbidden.status_code == 403
    assert service.calls == []

    accepted = client.post(
        "/api/smart-insights/refresh",
        headers=_authenticate(monkeypatch, user_id=3, role="admin"),
        json={"market": "macro", "sourceCodes": ["fred", "eia"]},
    )
    assert accepted.status_code == 202
    assert accepted.get_json()["data"] == {"status": "QUEUED", "runId": "run-1"}
    assert service.calls == [(3, "macro", ("fred", "eia"))]


def test_refresh_coordinator_dedupes_checksums_and_audits_counts():
    from app.services.smart_insights.collectors import RefreshCoordinator
    from app.services.smart_insights.contracts import Observation

    at = datetime(2026, 8, 24, 2, 0, tzinfo=timezone.utc)
    observation = Observation.create(
        source_code="fred",
        source_url="https://fred.stlouisfed.org/series/CPIAUCSL",
        market="macro",
        effective_at=at,
        observed_at=at,
        methodology_version="fred-cpi-v1",
        value={"metric": "macro.cpi", "value": "2.7"},
        data_class="LIVE",
    )

    class Repository:
        def __init__(self):
            self.seen = set()
            self.success = None

        def load_refresh_request(self, run_id):
            assert run_id == "run-1"
            return {"market": "macro", "sourceCodes": ("fred",)}

        def mark_run_running(self, run_id):
            assert run_id == "run-1"

        def resolve_data_source(self, code):
            assert code == "fred"
            return 4

        def upsert_observation(self, row, *, data_source_id, collector_run_id):
            assert data_source_id == 4
            assert collector_run_id == "run-1"
            created = row.checksum not in self.seen
            self.seen.add(row.checksum)
            return "obs-1", created

        def mark_run_succeeded(self, run_id, *, records_fetched, records_persisted, warnings):
            self.success = (run_id, records_fetched, records_persisted, warnings)

        def mark_run_failed(self, *_args, **_kwargs):
            pytest.fail("successful refresh was marked failed")

    repository = Repository()
    coordinator = RefreshCoordinator(
        repository=repository,
        collector_registry={"fred": lambda: (observation, observation)},
    )

    result = coordinator.execute("run-1")

    assert result == {
        "runId": "run-1",
        "status": "SUCCEEDED",
        "recordsFetched": 2,
        "recordsPersisted": 1,
        "warnings": [],
    }
    assert repository.success == ("run-1", 2, 1, ())


def test_refresh_coordinator_records_sanitized_failure():
    from app.services.smart_insights.collectors import CollectorUnavailable, RefreshCoordinator

    class Repository:
        failure = None

        def load_refresh_request(self, _run_id):
            return {"market": "macro", "sourceCodes": ("missing",)}

        def mark_run_running(self, _run_id):
            pass

        def mark_run_failed(self, run_id, *, error_code, warnings):
            self.failure = (run_id, error_code, warnings)

    repository = Repository()
    coordinator = RefreshCoordinator(repository=repository, collector_registry={})

    with pytest.raises(CollectorUnavailable, match="COLLECTOR_UNAVAILABLE"):
        coordinator.execute("run-2")
    assert repository.failure == (
        "run-2",
        "COLLECTOR_UNAVAILABLE",
        ("SOURCE_NOT_IMPLEMENTED:missing",),
    )


def test_refresh_coordinator_persists_runtime_rows_and_marks_import_only_sources_partial():
    from app.services.smart_insights.collectors import RefreshCoordinator
    from app.services.smart_insights.contracts import Observation

    at = datetime(2026, 8, 24, 2, 0, tzinfo=timezone.utc)
    observation = Observation.create(
        source_code="fred",
        source_url="https://fred.stlouisfed.org/series/CPIAUCSL",
        market="macro",
        effective_at=at,
        observed_at=at,
        methodology_version="fred-cpi-v1",
        value={"metric": "macro.cpi", "value": "2.7"},
        data_class="LIVE",
    )

    class Repository:
        result = None

        def load_refresh_request(self, _run_id):
            return {"market": "macro", "sourceCodes": ("fred", "farside-btc-etf")}

        def mark_run_running(self, _run_id):
            pass

        def resolve_data_source(self, code):
            return {"fred": 4, "farside-btc-etf": 5}[code]

        def upsert_observation(self, _row, *, data_source_id, collector_run_id):
            assert data_source_id == 4
            assert collector_run_id == "run-3"
            return "obs-1", True

        def mark_run_partial(self, run_id, *, records_fetched, records_persisted, warnings):
            self.result = (run_id, records_fetched, records_persisted, warnings)

        def mark_run_succeeded(self, *_args, **_kwargs):
            pytest.fail("partial refresh was marked succeeded")

        def mark_run_failed(self, *_args, **_kwargs):
            pytest.fail("partial refresh was marked failed")

    repository = Repository()
    result = RefreshCoordinator(
        repository=repository,
        collector_registry={"fred": lambda: (observation,)},
    ).execute("run-3")

    assert result["status"] == "PARTIAL"
    assert result["recordsFetched"] == 1
    assert "SOURCE_NOT_IMPLEMENTED:farside-btc-etf" in result["warnings"]
    assert repository.result[0:3] == ("run-3", 1, 1)


def test_evidence_grounded_explainer_rejects_demo_before_model_call():
    from app.services.smart_insights.explainer import EvidenceGroundedExplainer
    from app.services.smart_insights.contracts import EvidencePolicyError

    calls = []
    explainer = EvidenceGroundedExplainer(
        generate=lambda **kwargs: calls.append(kwargs) or "Dữ liệu vĩ mô đang hạ nhiệt."
    )
    live = {
        "id": "obs-1",
        "dataClass": "LIVE",
        "source": "fred",
        "sourceUrl": "https://fred.stlouisfed.org/series/CPIAUCSL",
        "observedAt": "2026-08-24T02:00:00+00:00",
        "effectiveAt": "2026-08-24T02:00:00+00:00",
        "methodologyVersion": "fred-cpi-v1",
        "checksum": "a" * 64,
    }

    text = explainer.explain(
        quantitative_summary={"regime": "cooling"}, evidence=[live], locale="vi"
    )
    assert text == "Dữ liệu vĩ mô đang hạ nhiệt."
    assert calls[0]["evidence"] == [live]

    with pytest.raises(EvidencePolicyError, match="DEMO_EVIDENCE_FORBIDDEN"):
        explainer.explain(
            quantitative_summary={"regime": "demo"},
            evidence=[{**live, "dataClass": "DEMO"}],
            locale="vi",
        )
    assert len(calls) == 1


def test_freshness_status_is_deterministic():
    from app.services.smart_insights.health import classify_freshness

    now = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)
    assert classify_freshness(None, now=now, sla_minutes=60) == "UNAVAILABLE"
    assert classify_freshness(
        datetime(2026, 8, 24, 3, 30, tzinfo=timezone.utc), now=now, sla_minutes=60
    ) == "FRESH"
    assert classify_freshness(
        datetime(2026, 8, 24, 2, 59, tzinfo=timezone.utc), now=now, sla_minutes=60
    ) == "STALE"


def test_all_market_overview_aggregates_market_scoped_snapshots(monkeypatch):
    from app.services.smart_insights.repository import SmartInsightsRepository

    snapshots = {
        "crypto": {
            "id": "crypto-snapshot",
            "asOf": "2026-08-25T07:16:08+00:00",
            "market": "crypto",
            "mode": "live",
            "status": "PARTIAL",
            "methodologyVersion": "datavest-smart-insights-v1",
            "evidenceChecksum": "a" * 64,
            "summary": {
                "sources": ["defillama-stablecoins"],
                "metrics": ["crypto.stablecoin.supply_usd"],
                "sourceCount": 1,
                "metricCount": 1,
                "observationCount": 3191,
                "directionalModelStatus": "UNAVAILABLE",
            },
            "opinions": [],
            "evidence": [{"id": "crypto-evidence", "role": "CONTEXT"}],
        },
        "vn": {
            "id": "vn-snapshot",
            "asOf": "2026-08-25T07:16:17+00:00",
            "market": "vn",
            "mode": "live",
            "status": "PARTIAL",
            "methodologyVersion": "datavest-smart-insights-v1",
            "evidenceChecksum": "b" * 64,
            "summary": {
                "sources": ["vn-provider"],
                "metrics": ["vn.index.close"],
                "sourceCount": 1,
                "metricCount": 1,
                "observationCount": 120,
                "directionalModelStatus": "UNAVAILABLE",
            },
            "opinions": [],
            "evidence": [{"id": "vn-evidence", "role": "CONTEXT"}],
        },
    }
    repository = SmartInsightsRepository()
    monkeypatch.setattr(
        repository,
        "get_overview",
        lambda **kwargs: snapshots.get(
            kwargs["market"],
            {
                "asOf": kwargs["as_of"],
                "market": kwargs["market"],
                "mode": kwargs["data_class"].lower(),
                "status": "UNAVAILABLE",
                "summary": {},
                "opinions": [],
            },
        ),
    )

    result = repository.get_overview_all(user_id=7, as_of=None, data_class="LIVE")

    assert result["market"] == "all"
    assert result["status"] == "PARTIAL"
    assert result["summary"] == {
        "sources": ["defillama-stablecoins", "vn-provider"],
        "metrics": ["crypto.stablecoin.supply_usd", "vn.index.close"],
        "sourceCount": 2,
        "metricCount": 2,
        "observationCount": 3311,
        "directionalModelStatus": "UNAVAILABLE",
    }
    assert [item["id"] for item in result["evidence"]] == [
        "crypto-evidence",
        "vn-evidence",
    ]
    assert len(result["evidenceChecksum"]) == 64
