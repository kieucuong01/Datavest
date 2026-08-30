import pytest


def test_registry_has_only_supported_markets():
    from app.markets.registry import list_market_keys

    assert list_market_keys() == ["USStock", "VNStock", "Crypto", "Forex"]


def test_factory_rejects_retired_market_without_crypto_fallback():
    from app.data_sources.factory import DataSourceFactory
    from app.utils.supported_markets import UnsupportedSupportedMarketError

    with pytest.raises(UnsupportedSupportedMarketError):
        DataSourceFactory.get_source("MOEX")

    with pytest.raises(UnsupportedSupportedMarketError):
        DataSourceFactory.get_source("")


def test_factory_exposes_vietnamese_stock_source():
    from app.data_sources.factory import DataSourceFactory

    source = DataSourceFactory.get_source("VNStock")
    assert source.name.startswith("VNStock/")


def test_forex_namespace_accepts_gold_only():
    from app.data_sources.forex import normalize_forex_pair_symbol

    assert normalize_forex_pair_symbol("XAU/USD") == "XAUUSD"
    with pytest.raises(ValueError):
        normalize_forex_pair_symbol("EURUSD")
