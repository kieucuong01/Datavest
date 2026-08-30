from app.data_sources.crypto import resolve_public_ccxt_market


def test_binance_swap_maps_to_public_usdm_ccxt():
    ccxt_id, _opts = resolve_public_ccxt_market("binance", "swap")
    assert ccxt_id == "binanceusdm"


def test_binance_spot_maps_to_public_spot_ccxt():
    ccxt_id, _opts = resolve_public_ccxt_market("binance", "spot")
    assert ccxt_id == "binance"


def test_public_resolver_normalizes_huobi_to_htx():
    ccxt_id, options = resolve_public_ccxt_market("huobi", "spot")
    assert ccxt_id == "htx"
    assert options["defaultType"] == "spot"
