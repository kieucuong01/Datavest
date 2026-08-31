"""Shared contracts for source-attributed crypto derivatives collectors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


UTC = timezone.utc
ASSETS = ("BTC", "ETH", "SOL")
OPTIONS_ASSETS = ("BTC", "ETH")

FUNDING_RATE = "crypto.derivatives.perpetual.funding_rate"
FUNDING_ANNUALIZED = "crypto.derivatives.perpetual.funding_annualized"
OI_USD = "crypto.derivatives.perpetual.open_interest_usd"
OI_NATIVE = "crypto.derivatives.perpetual.open_interest_native"
OI_CHANGE_PCT = "crypto.derivatives.perpetual.open_interest_change_pct"
LONG_SHORT_RATIO = "crypto.derivatives.perpetual.long_short_account_ratio"
TAKER_IMBALANCE = "crypto.derivatives.perpetual.taker_buy_sell_imbalance"
PERPETUAL_PRICE_USD = "crypto.derivatives.perpetual.price_usd"
NEAR_BASIS = "crypto.derivatives.futures.near_term_annualized_basis"
FAR_BASIS = "crypto.derivatives.futures.far_term_annualized_basis"
CALL_OI = "crypto.derivatives.options.call_open_interest"
PUT_OI = "crypto.derivatives.options.put_open_interest"
PUT_CALL_OI_RATIO = "crypto.derivatives.options.put_call_open_interest_ratio"
HISTORICAL_VOLATILITY = "crypto.derivatives.options.historical_volatility"


def daily_effective_at(as_of: datetime) -> datetime:
    """Return the fully closed UTC day represented by a daily collection."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    midnight = as_of.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=1)


@dataclass(frozen=True, slots=True)
class DerivativeBackfillRequest:
    source: str
    symbols: tuple[str, ...]
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("backfill range must be timezone-aware")
        if self.start > self.end:
            raise ValueError("backfill start must not be after end")


@dataclass(frozen=True, slots=True)
class DerivativeCoverage:
    source: str
    metric: str
    symbol: str
    start: datetime
    end: datetime
    history_limited: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "metric": self.metric,
            "symbol": self.symbol.upper(),
            "start": self.start.astimezone(UTC).isoformat(),
            "end": self.end.astimezone(UTC).isoformat(),
            "historyLimited": self.history_limited,
        }


__all__ = [
    "ASSETS",
    "CALL_OI",
    "DerivativeBackfillRequest",
    "DerivativeCoverage",
    "FAR_BASIS",
    "FUNDING_ANNUALIZED",
    "FUNDING_RATE",
    "HISTORICAL_VOLATILITY",
    "LONG_SHORT_RATIO",
    "NEAR_BASIS",
    "OI_CHANGE_PCT",
    "OI_NATIVE",
    "OI_USD",
    "OPTIONS_ASSETS",
    "PERPETUAL_PRICE_USD",
    "PUT_CALL_OI_RATIO",
    "PUT_OI",
    "TAKER_IMBALANCE",
    "daily_effective_at",
]
