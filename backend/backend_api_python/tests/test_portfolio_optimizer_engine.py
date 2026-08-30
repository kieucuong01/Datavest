"""Numerical contracts for the Python-native DataVest optimizer."""

from __future__ import annotations

import math

import numpy as np
import pytest


def price_matrix(rows: int = 121) -> tuple[list[str], np.ndarray]:
    returns = np.array(
        [
            [
                0.0012 + 0.0030 * math.sin(index / 7),
                0.0007 + 0.0020 * math.cos(index / 9),
                0.0003 + 0.0010 * math.sin(index / 13),
            ]
            for index in range(rows - 1)
        ],
        dtype=float,
    )
    prices = np.vstack([np.full(3, 100.0), 100.0 * np.cumprod(1.0 + returns, axis=0)])
    return ["BTC", "FPT", "AAPL"], prices


@pytest.mark.parametrize(
    "method,options",
    [
        ("risk_parity", {}),
        ("minimum_variance", {}),
        ("maximum_sharpe", {}),
        ("target_return", {"target_return_pct": 8.0}),
        ("target_volatility", {"target_volatility_pct": 18.0}),
        ("risk_tolerance", {"risk_tolerance": 2.0}),
    ],
)
def test_optimizer_methods_return_bounded_deterministic_allocations(method, options):
    from app.services.portfolio_optimizer.engine import OptimizerInput, optimize

    symbols, prices = price_matrix()
    request = OptimizerInput(
        symbols=tuple(symbols),
        prices=prices,
        method=method,
        max_weight=0.6,
        annualization=252,
        **options,
    )
    first = optimize(request)
    second = optimize(request)

    assert first == second
    assert sum(item["weightBps"] for item in first["allocations"]) == 10_000
    assert max(item["weightBps"] for item in first["allocations"]) <= 6_000
    assert first["observationCount"] == 121
    assert first["method"] == method
    assert len(first["correlationMatrix"]) == 3
    assert len(first["frontier"]) >= 5
    assert first["volatilityPct"] >= 0


def test_optimizer_enforces_v1_universe_and_history_limits():
    from app.services.portfolio_optimizer.engine import OptimizerInput, optimize

    symbols, prices = price_matrix(30)
    with pytest.raises(ValueError, match="31 synchronized prices"):
        optimize(OptimizerInput(tuple(symbols), prices, "minimum_variance"))

    eleven = np.full((31, 11), 100.0)
    with pytest.raises(ValueError, match="1 to 10 instruments"):
        optimize(OptimizerInput(tuple(f"S{i}" for i in range(11)), eleven, "risk_parity"))

    too_long = np.full((3651, 2), 100.0)
    with pytest.raises(ValueError, match="3,650"):
        optimize(OptimizerInput(("A", "B"), too_long, "risk_parity"))


def test_optimizer_rejects_missing_nonpositive_or_unaligned_prices():
    from app.services.portfolio_optimizer.engine import OptimizerInput, optimize

    symbols, prices = price_matrix()
    invalid = prices.copy()
    invalid[4, 1] = np.nan
    with pytest.raises(ValueError, match="finite and positive"):
        optimize(OptimizerInput(tuple(symbols), invalid, "minimum_variance"))

    with pytest.raises(ValueError, match="columns must match"):
        optimize(OptimizerInput(("BTC", "FPT"), prices, "minimum_variance"))
