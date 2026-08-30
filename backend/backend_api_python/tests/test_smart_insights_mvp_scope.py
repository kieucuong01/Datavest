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
