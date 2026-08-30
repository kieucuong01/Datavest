def test_filter_market_items_drops_hidden_retired_and_non_gold_forex_rows(monkeypatch):
    from app.utils.market_visibility import filter_market_items

    # Explicit configuration remains the controlled future re-enable path for
    # US stocks; the default product surface intentionally hides it.
    monkeypatch.setenv("ENABLED_MARKETS", "USStock,VNStock,Crypto,Forex")

    rows = [
        {"market": "USStock", "symbol": "AAPL"},
        {"market": "CNStock", "symbol": "600519"},
        {"market": "Forex", "symbol": "EURUSD"},
        {"market": "Forex", "symbol": "XAUUSD"},
    ]

    assert filter_market_items(rows, key="market") == [
        {"market": "USStock", "symbol": "AAPL"},
        {"market": "Forex", "symbol": "XAUUSD"},
    ]


def test_production_import_maps_gold_to_forex_namespace():
    from app.tools.import_production_account import infer_local_market

    assert infer_local_market({"symbol": "XAUUSD", "assetClass": "commodity"}) == "Forex"


def test_production_import_rejects_unsupported_forex_and_futures():
    from app.tools.import_production_account import infer_local_market
    from app.utils.supported_markets import UnsupportedSupportedMarketError

    import pytest

    with pytest.raises(UnsupportedSupportedMarketError):
        infer_local_market({"symbol": "EURUSD", "assetClass": "forex"})
    with pytest.raises(UnsupportedSupportedMarketError):
        infer_local_market({"symbol": "ES", "assetClass": "futures"})


def test_global_forex_and_commodity_catalogs_are_gold_only():
    from app.data_providers.commodities import COMMODITIES
    from app.data_providers.forex import FOREX_PAIRS

    assert len(FOREX_PAIRS) == 1
    assert FOREX_PAIRS[0]["td"] == "XAU/USD"
    assert len(COMMODITIES) == 1
    assert COMMODITIES[0]["name_en"] == "Gold"
