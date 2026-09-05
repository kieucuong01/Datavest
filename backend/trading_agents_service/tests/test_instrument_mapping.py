from __future__ import annotations

import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.instruments import InstrumentResolutionError, resolve_instrument


@pytest.mark.parametrize(
    ("market", "symbol", "ticker", "asset_type"),
    [
        ("Crypto", "BTC/USDT", "BTC-USD", "crypto"),
        ("VNStock", "VCB", "VCB.VN", "stock"),
        ("Gold", "XAU", "XAUUSD", "stock"),
    ],
)
def test_maps_datavest_instrument_to_upstream(
    market: str,
    symbol: str,
    ticker: str,
    asset_type: str,
) -> None:
    assert resolve_instrument(market, symbol) == (ticker, asset_type)


def test_rejects_unknown_or_path_like_instruments() -> None:
    with pytest.raises(InstrumentResolutionError, match="Unsupported"):
        resolve_instrument("Crypto", "BTC/EUR")
    with pytest.raises(InstrumentResolutionError, match="Unsupported"):
        resolve_instrument("VNStock", "../VCB")
