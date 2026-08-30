"""Provenance-bearing market-data contracts for optimizer inputs."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Instrument:
    market: str
    symbol: str
    currency: str
    exchange_id: str = ""
    market_type: str = ""


@dataclass(frozen=True, slots=True)
class PriceSeries:
    market: str
    symbol: str
    currency: str
    timestamps: tuple[int, ...]
    closes: tuple[float, ...]
    provider: str
    fallback_chain: tuple[str, ...]
    coverage: float
    checksum: str
    data_class: str = "LIVE"
    price_unit: str = ""
    mark_to_market_supported: bool = True


class MarketDataGateway(Protocol):
    def fetch_daily(self, instrument: Instrument, *, start_date: str, end_date: str) -> PriceSeries:
        ...

    def fetch_fx(
        self,
        source_currency: str,
        target_currency: str,
        *,
        start_date: str,
        end_date: str,
    ) -> PriceSeries | None:
        ...


def series_checksum(*, provider: str, timestamps, closes) -> str:
    payload = {
        "provider": provider,
        "timestamps": [int(value) for value in timestamps],
        "closes": [round(float(value), 12) for value in closes],
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = ["Instrument", "MarketDataGateway", "PriceSeries", "series_checksum"]
