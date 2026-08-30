import pytest


def test_only_product_markets_are_supported():
    from app.utils.supported_markets import SUPPORTED_MARKETS

    assert SUPPORTED_MARKETS == frozenset({"USStock", "VNStock", "Crypto", "Forex"})


def test_default_product_visibility_hides_us_stock_but_keeps_reenable_path(monkeypatch):
    monkeypatch.delenv("ENABLED_MARKETS", raising=False)

    from app.markets.registry import list_market_modules
    from app.utils.market_visibility import is_market_visible

    assert is_market_visible("USStock") is False
    assert is_market_visible("VNStock") is True
    assert is_market_visible("Crypto") is True
    assert is_market_visible("Forex") is True

    modules = {item["key"]: item for item in list_market_modules({})}
    assert modules["USStock"]["enabled"] is False
    assert [key for key, item in modules.items() if item["enabled"]] == ["VNStock", "Crypto", "Forex"]


def test_gold_aliases_are_canonicalized_to_xauusd():
    from app.utils.supported_markets import canonicalize_supported_symbol

    assert canonicalize_supported_symbol("Forex", "XAU") == "XAUUSD"
    assert canonicalize_supported_symbol("Forex", "XAU/USD") == "XAUUSD"
    assert canonicalize_supported_symbol("gold", "XAU-USD") == "XAUUSD"


def test_retired_market_is_rejected_without_crypto_fallback():
    from app.utils.supported_markets import (
        UnsupportedSupportedMarketError,
        normalize_supported_market,
    )

    with pytest.raises(UnsupportedSupportedMarketError):
        normalize_supported_market("Futures")


def test_non_gold_forex_symbol_is_rejected():
    from app.utils.supported_markets import (
        UnsupportedSupportedMarketError,
        canonicalize_supported_symbol,
    )

    with pytest.raises(UnsupportedSupportedMarketError):
        canonicalize_supported_symbol("Forex", "EURUSD")
