from __future__ import annotations


def test_imported_brief_is_watchlist_scoped_and_does_not_expose_unvalidated_ai_text():
    from app.services.smart_insights.production_account_view import build_imported_overview

    result = build_imported_overview(
        {
            "localDate": "2026-08-29",
            "assetOpinions": [
                {"symbol": "BTC/USDT", "thesis": "Imported BTC thesis", "stance": "POSITIVE"},
                {"symbol": "ETH/USDT", "thesis": "Imported ETH thesis", "stance": "NEUTRAL"},
            ],
        },
        checksum="a" * 64,
        market="all",
        watchlist_pairs=[{"market": "Crypto", "symbol": "BTC/USDT"}],
    )

    assert [item["symbol"] for item in result["opinions"]] == ["BTC"]
    assert result["opinions"][0]["evidenceValidated"] is False
    assert result["opinions"][0]["explanation"] is None


def test_smart_insights_service_applies_watchlist_scope_before_returning_imported_brief():
    from app.services.smart_insights.service import SmartInsightsService

    class Repository:
        def get_production_account_import(self, *, user_id, data_type):
            assert (user_id, data_type) == (17, "briefing")
            return {
                "payload": {
                    "localDate": "2026-08-29",
                    "assetOpinions": [
                        {"symbol": "BTC/USDT", "thesis": "BTC", "stance": "POSITIVE"},
                        {"symbol": "XAUUSD", "thesis": "Gold", "stance": "NEUTRAL"},
                    ],
                },
                "checksum": "b" * 64,
            }

    service = SmartInsightsService(
        repository=Repository(),
        watchlist_loader=lambda user_id: [{"market": "Crypto", "symbol": "BTC/USDT"}],
    )

    result = service.get_overview(user_id=17, as_of=None, market="all", mode="live")

    assert [item["symbol"] for item in result["opinions"]] == ["BTC"]


def test_smart_insights_service_prefers_latest_live_snapshot_over_stale_import():
    from app.services.smart_insights.service import SmartInsightsService

    calls = []

    class Repository:
        def list_dates(self, *, market, data_class):
            calls.append(("list_dates", market, data_class))
            return ["2026-09-02", "2026-09-01"]

        def get_production_account_import(self, *, user_id, data_type):
            assert (user_id, data_type) == (17, "briefing")
            return {
                "payload": {
                    "localDate": "2026-08-26",
                    "assetOpinions": [{"symbol": "BTC", "thesis": "stale"}],
                },
                "checksum": "c" * 64,
            }

        def get_overview_all(self, **kwargs):
            calls.append(("get_overview_all", kwargs))
            return {"asOf": "2026-09-02", "status": "COMPLETE", "opinions": []}

    result = SmartInsightsService(
        repository=Repository(),
        watchlist_loader=lambda user_id: [{"market": "Crypto", "symbol": "BTC/USDT"}],
    ).get_overview(user_id=17, as_of=None, market="all", mode="live")

    assert result["asOf"] == "2026-09-02"
    assert calls[0] == ("list_dates", None, "LIVE")
    assert calls[1][0] == "get_overview_all"


def test_smart_insights_dates_treat_all_as_an_unfiltered_market_union():
    from app.services.smart_insights.service import SmartInsightsService

    calls = []

    class Repository:
        def list_dates(self, *, market, data_class):
            calls.append((market, data_class))
            return ["2026-09-02", "2026-09-01"]

        def get_production_account_import(self, *, user_id, data_type):
            return {"payload": {"localDate": "2026-08-26"}, "checksum": "d" * 64}

    result = SmartInsightsService(repository=Repository()).list_dates(
        user_id=17, market="all", mode="live"
    )

    assert calls == [(None, "LIVE")]
    assert result["dates"] == ["2026-09-02", "2026-09-01", "2026-08-26"]


def test_evidence_response_includes_deterministic_reliability_label():
    from app.services.smart_insights.repository import SmartInsightsRepository

    row = {
        "id": "obs-1",
        "market": "crypto",
        "symbol": "BTC",
        "source_code": "coinglass",
        "source_url": "https://example.test/source",
        "effective_at": None,
        "published_at": None,
        "observed_at": None,
        "methodology_version": "v1",
        "warnings_json": "[]",
        "checksum": "a" * 64,
        "data_class": "LIVE",
        "value_json": "{}",
    }

    result = SmartInsightsRepository._evidence_row(row)

    assert result["reliability"] == "HIGH"
