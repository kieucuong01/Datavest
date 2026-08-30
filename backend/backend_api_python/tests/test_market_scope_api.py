def test_market_types_are_restricted(client):
    response = client.get("/api/market/types")

    assert response.status_code == 200
    assert [item["value"] for item in response.get_json()["data"]] == [
        "VNStock",
        "Crypto",
        "Forex",
    ]


def test_watchlist_rejects_retired_market():
    from app.services.market.watchlist import validate_watchlist_pair

    assert "Unsupported market" in validate_watchlist_pair("HKStock", "0700")


def test_symbol_search_never_returns_retired_market_rows():
    from app.services.market.symbol_search import dedupe_symbol_results

    assert dedupe_symbol_results([{"market": "MOEX", "symbol": "SBER"}], 20) == []


def test_symbol_search_rejects_retired_market(client):
    response = client.get("/api/market/symbols/search?market=Futures&keyword=ES")

    assert response.status_code == 400
    assert response.get_json()["code"] == 0


def test_gold_search_rows_are_canonicalized():
    from app.services.market.symbol_search import dedupe_symbol_results

    rows = dedupe_symbol_results(
        [{"market": "gold", "symbol": "XAU/USD", "name": "Gold"}],
        20,
    )
    assert rows[0]["market"] == "Forex"
    assert rows[0]["symbol"] == "XAUUSD"


def test_symbol_search_derives_asset_class_from_supported_market():
    from app.services.market.symbol_search import dedupe_symbol_results

    rows = dedupe_symbol_results(
        [
            {"market": "USStock", "symbol": "AAPL", "name": "Apple"},
            {"market": "VNStock", "symbol": "FPT", "name": "FPT"},
            {"market": "Forex", "symbol": "XAUUSD", "name": "Gold"},
        ],
        20,
    )

    assert [row["asset_class"] for row in rows] == ["equity", "equity", "commodity"]
