"""Anonymous read boundaries for Smart Insights and the economic calendar."""

from __future__ import annotations

from copy import deepcopy


class PublicRepositoryDouble:
    def __init__(self):
        self.overview_calls = []
        self.production_import_calls = []

    def get_overview_all(self, **kwargs):
        self.overview_calls.append(deepcopy(kwargs))
        return {
            "status": "AVAILABLE",
            "asOf": kwargs.get("as_of") or "2026-09-12",
            "opinions": [
                {"market": "crypto", "symbol": "BTC", "stance": "neutral"},
                {"market": "vn", "symbol": "VNINDEX", "stance": "positive"},
                {"market": "gold", "symbol": "XAU", "stance": "neutral"},
                {"market": "us", "symbol": "AAPL", "stance": "positive"},
            ],
        }

    def get_production_account_import(self, **kwargs):
        self.production_import_calls.append(deepcopy(kwargs))
        raise AssertionError("public service must not read tenant imports")

    def list_dates(self, **kwargs):
        return ["2026-09-12", "2026-09-11"]

    def get_evidence(self, evidence_id):
        return {
            "id": evidence_id,
            "market": "crypto",
            "symbol": "BTC",
            "source": "source-code",
            "sourceName": "Source",
            "sourceUrl": "https://example.com/source",
            "effectiveAt": "2026-09-12T00:00:00+00:00",
            "publishedAt": None,
            "observedAt": "2026-09-12T00:05:00+00:00",
            "methodologyVersion": "v1",
            "warnings": [],
            "checksum": "a" * 64,
            "dataClass": "LIVE",
            "reliability": "high",
            "value": {
                "metric": "price",
                "value": "100",
                "unit": "USD",
                "dimensions": {
                    "fund": "IBIT",
                    "frequency": "daily",
                    "prompt": "nested prompt must not leak",
                    "request_json": {"secret": "nested secret"},
                },
                "request_json": {"secret": "must-not-leak"},
                "credentials": {"api_key": "must-not-leak"},
                "prompt": "must-not-leak",
            },
            "user_id": 77,
            "request_json": {"secret": "must-not-leak"},
        }

    def data_health(self):
        return [
            {
                "code": "source-code",
                "name": "Source",
                "market": "crypto",
                "sourceUrl": "https://example.com/source",
                "freshness": "FRESH",
                "lastObservedAt": "2026-09-12T00:05:00+00:00",
                "coverage": {"liveObservations30d": 12},
                "disabledReason": "internal detail",
                "lastRun": {"status": "FAILED", "errorCode": "PRIVATE_ERROR"},
            }
        ]

    def list_pulse_observations(self, **kwargs):
        return []


def test_public_service_uses_only_fixed_shared_assets_and_never_tenant_imports():
    from app.services.smart_insights.public_access import (
        PUBLIC_ASSET_SCOPE,
        PublicSmartInsightsService,
    )

    repository = PublicRepositoryDouble()
    result = PublicSmartInsightsService(repository=repository).get_overview(
        as_of="2026-09-12", locale="vi-VN"
    )

    assert [item["displaySymbol"] for item in PUBLIC_ASSET_SCOPE] == [
        "BTC",
        "VNINDEX",
        "XAU",
    ]
    assert [item["displaySymbol"] for item in result["assets"]] == [
        "BTC",
        "VNINDEX",
        "XAU",
    ]
    assert [item["symbol"] for item in result["opinions"]] == [
        "BTC",
        "VNINDEX",
        "XAU",
    ]
    assert repository.production_import_calls == []
    assert repository.overview_calls == [
        {
            "user_id": 0,
            "as_of": "2026-09-12",
            "data_class": "LIVE",
            "watchlist_pairs": [dict(item) for item in PUBLIC_ASSET_SCOPE],
        }
    ]


def test_public_evidence_and_health_remove_internal_fields():
    from app.services.smart_insights.public_access import PublicSmartInsightsService

    service = PublicSmartInsightsService(repository=PublicRepositoryDouble())
    evidence = service.get_evidence("obs-1")
    health = service.get_data_health()

    assert evidence["id"] == "obs-1"
    assert evidence["dataClass"] == "LIVE"
    assert "user_id" not in evidence
    assert "request_json" not in evidence
    assert evidence["value"] == {
        "metric": "price",
        "value": "100",
        "unit": "USD",
        "dimensions": {"fund": "IBIT", "frequency": "daily"},
    }
    assert health["sources"][0]["freshness"] == "FRESH"
    assert "disabledReason" not in health["sources"][0]
    assert "lastRun" not in health["sources"][0]


def test_public_evidence_rejects_non_live_rows_and_unbounded_ids():
    from app.services.smart_insights.public_access import PublicSmartInsightsService

    repository = PublicRepositoryDouble()
    service = PublicSmartInsightsService(repository=repository)
    repository.get_evidence = lambda _evidence_id: {"id": "demo", "dataClass": "DEMO"}

    assert service.get_evidence("demo") is None

    try:
        service.get_evidence("x" * 129)
    except ValueError as exc:
        assert str(exc) == "invalid_evidence_id"
    else:
        raise AssertionError("oversized evidence id must be rejected")


def test_public_routes_are_anonymous_while_private_routes_still_require_jwt(
    client, monkeypatch
):
    from app.routes import smart_insights as routes

    class PublicService:
        def get_overview(self, **_kwargs):
            return {"status": "AVAILABLE", "assets": [], "opinions": []}

        def list_dates(self):
            return {"mode": "live", "dates": []}

        def get_evidence(self, evidence_id):
            return {"id": evidence_id, "dataClass": "LIVE"}

        def get_data_health(self):
            return {"status": "AVAILABLE", "sources": []}

        def get_live_assets(self):
            return {"assets": [], "fetchedAt": "2026-09-12T00:00:00+00:00"}

        def get_crypto_market_pulse(self, **_kwargs):
            return {"status": "UNAVAILABLE", "tabs": {}}

    monkeypatch.setattr(
        routes, "get_public_smart_insights_service", lambda: PublicService()
    )

    public_paths = (
        "/api/smart-insights/public/overview",
        "/api/smart-insights/public/dates",
        "/api/smart-insights/public/evidence/obs-1",
        "/api/smart-insights/public/data-health",
        "/api/smart-insights/public/live-assets",
        "/api/smart-insights/public/crypto-market-pulse",
    )
    for path in public_paths:
        response = client.get(path)
        assert response.status_code == 200, path

    assert client.get("/api/smart-insights/overview").status_code == 401
    assert client.get("/api/smart-insights/crypto-market-pulse").status_code == 401
    assert client.post("/api/smart-insights/refresh", json={}).status_code == 401


def test_public_report_route_is_anonymous_and_fixed_to_the_common_asset_scope(
    client, monkeypatch
):
    from app.routes import smart_insights as routes

    class PublicService:
        def get_public_report(self, *, asset_key, report_kind, locale):
            assert (asset_key, report_kind, locale) == (
                "crypto:BTC/USDT",
                "quick",
                "vi-VN",
            )
            return {
                "assetKey": asset_key,
                "reportKind": report_kind,
                "title": "BTC",
            }

    monkeypatch.setattr(
        routes, "get_public_smart_insights_service", lambda: PublicService()
    )

    response = client.get(
        "/api/smart-insights/public/reports/crypto:BTC%2FUSDT/quick?lang=vi-VN"
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["assetKey"] == "crypto:BTC/USDT"


def test_public_report_route_rejects_an_asset_outside_the_common_scope(client):
    response = client.get(
        "/api/smart-insights/public/reports/crypto:ETH%2FUSDT/quick?runId=private"
    )

    assert response.status_code == 404
    assert "private" not in response.get_data(as_text=True)


def test_public_deep_report_pdf_renders_only_the_sanitized_published_payload(
    client, monkeypatch
):
    from app.routes import smart_insights as routes

    rendered = []

    class PublicService:
        def get_public_report(self, *, asset_key, report_kind, locale):
            assert (asset_key, report_kind, locale) == (
                "crypto:BTC/USDT",
                "deep",
                "vi-VN",
            )
            return {
                "assetKey": asset_key,
                "reportKind": report_kind,
                "effectiveDate": "2026-09-13",
                "title": "Phân tích chuyên sâu BTC",
                "body": "# BTC\n\nNội dung công khai đã lọc.",
            }

    monkeypatch.setattr(
        routes, "get_public_smart_insights_service", lambda: PublicService()
    )
    monkeypatch.setattr(
        routes,
        "build_trading_agents_report_pdf",
        lambda **kwargs: rendered.append(kwargs) or b"%PDF-1.4 public",
    )

    response = client.get(
        "/api/smart-insights/public/reports/crypto:BTC%2FUSDT/deep.pdf?lang=en-US"
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data == b"%PDF-1.4 public"
    assert "source_run_id" not in rendered[0]
    assert rendered[0] == {
        "content": "# BTC\n\nNội dung công khai đã lọc.",
        "market": "Crypto",
        "symbol": "BTC/USDT",
        "analysis_date": "2026-09-13",
        "language": "vi-VN",
        "run_id": "public-report",
    }


def test_public_deep_report_pdf_does_not_render_an_empty_report(client, monkeypatch):
    from app.routes import smart_insights as routes

    class PublicService:
        def get_public_report(self, **_kwargs):
            return {"assetKey": "crypto:BTC/USDT", "reportKind": "deep", "body": "  "}

    monkeypatch.setattr(
        routes, "get_public_smart_insights_service", lambda: PublicService()
    )

    response = client.get(
        "/api/smart-insights/public/reports/crypto:BTC%2FUSDT/deep.pdf"
    )

    assert response.status_code == 404
    assert response.get_json()["msg"] == "public_report_not_found"


def test_public_deep_summary_pdf_renders_the_sanitized_published_payload(
    client, monkeypatch
):
    from app.routes import smart_insights as routes

    rendered = []

    class PublicService:
        def get_public_report(self, *, asset_key, report_kind, locale):
            assert (asset_key, report_kind, locale) == (
                "crypto:BTC/USDT",
                "deep",
                "vi-VN",
            )
            return {
                "assetKey": asset_key,
                "reportKind": report_kind,
                "effectiveDate": "2026-09-13",
                "body": "# BTC\n\nNội dung công khai đã lọc.",
            }

    monkeypatch.setattr(
        routes, "get_public_smart_insights_service", lambda: PublicService()
    )
    monkeypatch.setattr(
        routes,
        "build_trading_agents_summary_pdf",
        lambda **kwargs: rendered.append(kwargs) or b"%PDF-1.4 public summary",
    )

    response = client.get(
        "/api/smart-insights/public/reports/crypto:BTC%2FUSDT/deep-summary.pdf"
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data == b"%PDF-1.4 public summary"
    assert rendered[0]["content"] == "# BTC\n\nNội dung công khai đã lọc."
    assert rendered[0]["run_id"] == "public-report"


def test_public_calendar_is_anonymous_but_cannot_force_refresh(client, monkeypatch):
    from app.routes import global_market as routes

    payload = {
        "events": [
            {
                "date": "2026-09-12",
                "time": "19:30",
                "country": "US",
                "event": "CPI",
                "importance": "high",
            }
        ],
        "meta": {"status": "ok", "source": "investing_browser"},
    }
    monkeypatch.setattr(routes, "get_economic_calendar_payload", lambda: payload)
    monkeypatch.setattr(
        routes,
        "cached_or_compute",
        lambda _key, loader, **_kwargs: loader(),
    )

    response = client.get("/api/global-market/public/calendar")
    assert response.status_code == 200
    assert response.get_json()["data"][0]["event"] == "CPI"

    forced = client.get("/api/global-market/public/calendar?force=1")
    assert forced.status_code == 400
    assert forced.get_json()["msg"] == "force_refresh_requires_auth"

    assert client.get("/api/global-market/calendar").status_code == 401


def test_public_calendar_does_not_expose_internal_exception_text(client, monkeypatch):
    from app.routes import global_market as routes

    def fail_loader(*_args, **_kwargs):
        raise RuntimeError("postgresql://internal-user:secret@postgres/datavest")

    monkeypatch.setattr(routes, "cached_or_compute", fail_loader)

    response = client.get("/api/global-market/public/calendar")
    body = response.get_json()

    assert response.status_code == 500
    assert body == {
        "code": 0,
        "msg": "economic_calendar_unavailable",
        "data": None,
    }
