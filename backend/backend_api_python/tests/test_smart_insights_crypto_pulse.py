from __future__ import annotations

from datetime import datetime, timezone


def _observation(
    source: str,
    metric: str,
    value: str,
    *,
    effective_at: str = "2026-08-24T00:00:00+00:00",
    symbol: str | None = None,
    dimensions: dict | None = None,
):
    return {
        "id": f"{source}-{metric}-{symbol or 'global'}-{effective_at}",
        "source": source,
        "sourceUrl": f"https://example.test/{source}",
        "market": "crypto" if source != "cryptocraft" else "macro",
        "symbol": symbol,
        "effectiveAt": effective_at,
        "observedAt": "2026-08-25T01:00:00+00:00",
        "methodologyVersion": f"{source}-v1",
        "dataClass": "LIVE",
        "checksum": "a" * 64,
        "warnings": [],
        "value": {
            "metric": metric,
            "value": value,
            "unit": "USD" if "flow" in metric else "index",
            "dimensions": dimensions or {},
        },
    }


def test_crypto_pulse_groups_persisted_evidence_by_legacy_tab_without_inventing_values():
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation("alternative-fng", "crypto.fear_greed.index", "66"),
        _observation("farside-btc-etf", "crypto.etf.net_flow_usd", "501000000", symbol="BTC", dimensions={"fund": "TOTAL"}),
        _observation("farside-eth-etf", "crypto.etf.net_flow_usd", "12000000", symbol="ETH", dimensions={"fund": "TOTAL"}),
        _observation("defillama-stablecoins", "crypto.stablecoin.supply_usd", "180000000000"),
        _observation("mempool-space", "crypto.mempool.tx_count", "190234"),
        _observation("blockchaincenter-altcoin-season", "crypto.cycle.altcoin_season.index", "41"),
        _observation("cbbi-public", "crypto.cycle.cbbi.confidence", "54"),
        _observation("cryptocraft", "macro.calendar.event", "1", dimensions={"event": "US CPI", "impact": "high"}),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            assert data_class == "LIVE"
            assert as_of is None
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    assert result["mode"] == "live"
    assert result["status"] == "PARTIAL"
    assert result["tabs"]["sentimentDerivatives"]["fearGreed"]["latest"]["value"] == 66
    assert result["tabs"]["flows"]["etfFlows"]["summaries"] == [
        {"asset": "BTC", "latest": 501000000.0, "effectiveAt": "2026-08-24T00:00:00+00:00"},
        {"asset": "ETH", "latest": 12000000.0, "effectiveAt": "2026-08-24T00:00:00+00:00"},
    ]
    assert {item["metric"] for item in result["tabs"]["onchain"]["metrics"]} == {
        "crypto.mempool.tx_count",
        "crypto.stablecoin.supply_usd",
    }
    assert result["tabs"]["whales"]["status"] == "UNAVAILABLE"
    assert "btcBottom" not in result["tabs"]
    assert result["calendar"]["events"] == [
        {"effectiveAt": "2026-08-24T00:00:00+00:00", "event": "US CPI", "impact": "high", "source": "cryptocraft"}
    ]


def test_crypto_pulse_rejects_demo_evidence_and_keeps_empty_tabs_unavailable():
    from app.services.smart_insights.service import SmartInsightsService

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            assert data_class == "DEMO"
            return []

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of="2026-08-24", mode="demo"
    )

    assert result["status"] == "UNAVAILABLE"
    assert {tab["status"] for tab in result["tabs"].values()} == {"UNAVAILABLE"}
    assert result["calendar"]["events"] == []


def test_crypto_pulse_route_requires_jwt_and_passes_validated_inputs(client, monkeypatch):
    from app.routes import smart_insights as routes

    captured = {}

    class Service:
        def get_crypto_market_pulse(self, *, user_id, as_of, mode):
            captured.update(user_id=user_id, as_of=as_of, mode=mode)
            return {"status": "UNAVAILABLE", "tabs": {}, "calendar": {"events": []}}

    monkeypatch.setattr(routes, "get_smart_insights_service", lambda: Service())

    unauthorized = client.get("/api/smart-insights/crypto-market-pulse")
    assert unauthorized.status_code == 401

    monkeypatch.setattr(
        "app.utils.auth.verify_token",
        lambda _raw: {
            "sub": "researcher",
            "user_id": 41,
            "role": "user",
            "_verified_username": "researcher",
            "_verified_user_role": "user",
        },
    )
    response = client.get(
        "/api/smart-insights/crypto-market-pulse?as_of=2026-08-24&mode=live",
        headers={"Authorization": "Bearer research-jwt"},
    )

    assert response.status_code == 200
    assert captured == {"user_id": 41, "as_of": "2026-08-24", "mode": "live"}
