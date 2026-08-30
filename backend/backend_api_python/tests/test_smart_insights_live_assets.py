from app.services.smart_insights.live_assets import (
    LIVE_ASSET_CATALOG,
    get_live_asset_snapshot,
)


def _authenticate(monkeypatch):
    from app.utils import auth as core_auth

    monkeypatch.setattr(
        core_auth,
        "verify_token",
        lambda _raw: {
            "sub": "researcher",
            "user_id": 7,
            "role": "user",
            "_verified_username": "researcher",
            "_verified_user_role": "user",
        },
    )
    return {"Authorization": "Bearer test-jwt"}


def test_live_asset_catalog_has_the_exact_product_order():
    assert [item["displaySymbol"] for item in LIVE_ASSET_CATALOG] == [
        "BTC",
        "ETH",
        "SOL",
        "XRP",
        "LINK",
        "VNINDEX",
        "VN30",
        "XAU",
    ]
    assert LIVE_ASSET_CATALOG[-1] == {
        "displaySymbol": "XAU",
        "market": "Forex",
        "symbol": "XAUUSD",
    }


def test_live_asset_snapshot_preserves_unavailable_and_stale_truth():
    def fetcher(items, timeout_sec):
        assert timeout_sec == 12
        assert items == list(LIVE_ASSET_CATALOG)
        return [
            {
                "market": "Crypto",
                "symbol": "BTC/USDT",
                "price": 77000,
                "change": 100,
                "changePercent": 0.13,
                "source": "ticker",
            },
            {
                "market": "Forex",
                "symbol": "XAUUSD",
                "price": 4500,
                "change": -10,
                "changePercent": -0.22,
                "source": "ticker",
                "cached": True,
                "stale": True,
            },
        ]

    result = get_live_asset_snapshot(
        quote_fetcher=fetcher,
        fetched_at="2026-08-29T00:00:00+00:00",
    )
    by_symbol = {row["displaySymbol"]: row for row in result["assets"]}
    assert by_symbol["BTC"]["status"] == "LIVE"
    assert by_symbol["XAU"]["status"] == "STALE"
    assert by_symbol["ETH"]["status"] == "UNAVAILABLE"
    assert by_symbol["ETH"]["price"] == 0


def test_live_asset_route_requires_jwt_and_returns_bounded_snapshot(client, monkeypatch):
    assert client.get("/api/smart-insights/live-assets").status_code == 401

    from app.services.smart_insights import live_assets as live_assets_service

    monkeypatch.setattr(
        live_assets_service,
        "get_live_asset_snapshot",
        lambda: {"fetchedAt": "2026-08-29T00:00:00+00:00", "assets": []},
    )
    response = client.get(
        "/api/smart-insights/live-assets",
        headers=_authenticate(monkeypatch),
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "code": 1,
        "msg": "success",
        "data": {"fetchedAt": "2026-08-29T00:00:00+00:00", "assets": []},
    }


def test_live_asset_route_hides_provider_exception(client, monkeypatch):
    from app.services.smart_insights import live_assets as live_assets_service

    def fail():
        raise RuntimeError("provider key must not reach the client")

    monkeypatch.setattr(live_assets_service, "get_live_asset_snapshot", fail)
    response = client.get(
        "/api/smart-insights/live-assets",
        headers=_authenticate(monkeypatch),
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "code": 0,
        "msg": "smart_insights_live_assets_unavailable",
        "data": None,
    }
