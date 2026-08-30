"""Deterministic long-only optimizer with no TypeScript or external solver runtime."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any, Callable

import numpy as np


METHODS = frozenset(
    {
        "risk_parity",
        "minimum_variance",
        "maximum_sharpe",
        "target_return",
        "target_volatility",
        "risk_tolerance",
    }
)


@dataclass(frozen=True, slots=True)
class OptimizerInput:
    symbols: tuple[str, ...]
    prices: np.ndarray
    method: str
    max_weight: float = 1.0
    annualization: int = 252
    target_return_pct: float | None = None
    target_volatility_pct: float | None = None
    risk_tolerance: float | None = None


def _project_capped_simplex(values: np.ndarray, cap: float) -> np.ndarray:
    count = len(values)
    if cap * count < 1 - 1e-12:
        raise ValueError("Maximum weight cannot satisfy a fully invested portfolio.")
    low = float(np.min(values) - cap)
    high = float(np.max(values))
    for _ in range(100):
        middle = (low + high) / 2
        weights = np.clip(values - middle, 0.0, cap)
        if float(weights.sum()) > 1:
            low = middle
        else:
            high = middle
    weights = np.clip(values - high, 0.0, cap)
    residual = 1.0 - float(weights.sum())
    if abs(residual) > 1e-10:
        for index in np.argsort(values)[::-1]:
            room = cap - weights[index] if residual > 0 else weights[index]
            delta = np.sign(residual) * min(abs(residual), room)
            weights[index] += delta
            residual -= delta
            if abs(residual) <= 1e-12:
                break
    return weights


def _gradient_descent(
    gradient: Callable[[np.ndarray], np.ndarray],
    count: int,
    cap: float,
    *,
    iterations: int = 600,
) -> np.ndarray:
    weights = _project_capped_simplex(np.full(count, 1 / count), cap)
    for index in range(iterations):
        grad = np.asarray(gradient(weights), dtype=float)
        if not np.isfinite(grad).all():
            raise ValueError("Optimizer produced a non-finite gradient.")
        norm = float(np.linalg.norm(grad))
        if norm <= 1e-14:
            break
        step = 0.08 / sqrt(index + 1)
        updated = _project_capped_simplex(weights - step * grad / norm, cap)
        if float(np.max(np.abs(updated - weights))) <= 1e-11:
            weights = updated
            break
        weights = updated
    return weights


def _risk_parity(covariance: np.ndarray, cap: float) -> np.ndarray:
    count = covariance.shape[0]
    weights = _project_capped_simplex(1 / np.sqrt(np.diag(covariance)), cap)
    for _ in range(600):
        marginal = covariance @ weights
        total_variance = float(weights @ marginal)
        target = total_variance / count
        contributions = np.maximum(weights * marginal, 1e-18)
        updated = _project_capped_simplex(weights * np.sqrt(target / contributions), cap)
        if float(np.max(np.abs(updated - weights))) <= 1e-11:
            return updated
        weights = 0.5 * weights + 0.5 * updated
    return _project_capped_simplex(weights, cap)


def _solve(
    method: str,
    mean: np.ndarray,
    covariance: np.ndarray,
    cap: float,
    request: OptimizerInput,
) -> np.ndarray:
    count = len(mean)
    if method == "risk_parity":
        return _risk_parity(covariance, cap)
    if method == "minimum_variance":
        return _gradient_descent(lambda w: 2 * covariance @ w, count, cap)
    if method == "maximum_sharpe":
        def sharpe_gradient(w):
            variance = max(float(w @ covariance @ w), 1e-18)
            volatility = sqrt(variance)
            expected = float(mean @ w)
            return -(mean / volatility - expected * (covariance @ w) / (volatility ** 3))
        return _gradient_descent(sharpe_gradient, count, cap)
    if method == "target_return":
        if request.target_return_pct is None:
            raise ValueError("Target return is required.")
        target = request.target_return_pct / 100
        penalty = 500.0
        return _gradient_descent(
            lambda w: 2 * covariance @ w
            - (2 * penalty * max(0.0, target - float(mean @ w))) * mean,
            count,
            cap,
        )
    if method == "target_volatility":
        if request.target_volatility_pct is None or request.target_volatility_pct <= 0:
            raise ValueError("Target volatility is required.")
        target_variance = (request.target_volatility_pct / 100) ** 2
        penalty = 500.0
        return _gradient_descent(
            lambda w: -mean
            + 4 * penalty * max(0.0, float(w @ covariance @ w) - target_variance)
            * (covariance @ w),
            count,
            cap,
        )
    if method == "risk_tolerance":
        if request.risk_tolerance is None or request.risk_tolerance <= 0:
            raise ValueError("Risk tolerance is required.")
        risk_aversion = 1 / request.risk_tolerance
        return _gradient_descent(
            lambda w: 2 * risk_aversion * (covariance @ w) - mean,
            count,
            cap,
        )
    raise ValueError(f"Unsupported optimizer method: {method}.")


def _basis_points(symbols: tuple[str, ...], weights: np.ndarray) -> dict[str, int]:
    raw = weights * 10_000
    rounded = np.floor(raw).astype(int)
    remainder = 10_000 - int(rounded.sum())
    order = sorted(range(len(symbols)), key=lambda i: (-(raw[i] - rounded[i]), symbols[i]))
    for index in order[:remainder]:
        rounded[index] += 1
    return {symbol: int(rounded[index]) for index, symbol in enumerate(symbols)}


def _portfolio_metrics(mean, covariance, weights) -> dict[str, float | None]:
    expected = float(mean @ weights)
    volatility = sqrt(max(float(weights @ covariance @ weights), 0.0))
    return {
        "expectedReturnPct": round(expected * 100, 4),
        "volatilityPct": round(volatility * 100, 4),
        "sharpe": None if volatility <= 1e-12 else round(expected / volatility, 6),
    }


def _frontier(mean: np.ndarray, covariance: np.ndarray, cap: float) -> list[dict[str, float]]:
    minimum_variance = _gradient_descent(
        lambda w: 2 * covariance @ w,
        len(mean),
        cap,
        iterations=600,
    )
    maximum_return = _project_capped_simplex(mean * 10_000, cap)
    points: list[dict[str, float]] = []
    for alpha in np.linspace(0.0, 1.0, 9):
        weights = _project_capped_simplex(
            (1 - float(alpha)) * minimum_variance + float(alpha) * maximum_return,
            cap,
        )
        metrics = _portfolio_metrics(mean, covariance, weights)
        points.append(
            {
                "expectedReturnPct": float(metrics["expectedReturnPct"] or 0),
                "volatilityPct": float(metrics["volatilityPct"] or 0),
            }
        )
    unique = {(point["volatilityPct"], point["expectedReturnPct"]): point for point in points}
    return [unique[key] for key in sorted(unique)]


def optimize(request: OptimizerInput) -> dict[str, Any]:
    prices = np.asarray(request.prices, dtype=float)
    if prices.ndim != 2 or prices.shape[1] != len(request.symbols):
        raise ValueError("Price columns must match symbols.")
    if not 1 <= len(request.symbols) <= 10:
        raise ValueError("Expected 1 to 10 instruments.")
    if not 31 <= prices.shape[0]:
        raise ValueError("Optimizer requires at least 31 synchronized prices.")
    if prices.shape[0] > 3_650:
        raise ValueError("Optimizer supports at most 3,650 daily prices.")
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("Prices must be finite and positive.")
    if len(set(request.symbols)) != len(request.symbols) or any(not str(s).strip() for s in request.symbols):
        raise ValueError("Symbols must be unique and non-empty.")
    if request.method not in METHODS:
        raise ValueError("Unsupported optimizer method.")
    if not 0 < request.max_weight <= 1:
        raise ValueError("Maximum weight must be between zero and one.")
    if request.annualization <= 0:
        raise ValueError("Annualization must be positive.")

    order = np.argsort(np.asarray(request.symbols, dtype=str))
    symbols = tuple(request.symbols[index] for index in order)
    prices = prices[:, order]
    returns = prices[1:] / prices[:-1] - 1
    mean = np.mean(returns, axis=0) * request.annualization
    covariance = np.atleast_2d(np.cov(returns, rowvar=False, ddof=1)) * request.annualization
    covariance = covariance + np.eye(len(symbols)) * 1e-12
    weights = _solve(request.method, mean, covariance, request.max_weight, request)
    bps = _basis_points(symbols, weights)
    effective = np.asarray([bps[symbol] / 10_000 for symbol in symbols])
    metrics = _portfolio_metrics(mean, covariance, effective)
    correlation = np.atleast_2d(np.corrcoef(returns, rowvar=False))
    correlation = np.nan_to_num(correlation, nan=0.0)
    np.fill_diagonal(correlation, 1.0)
    return {
        "method": request.method,
        "source": {"library": "numpy", "version": np.__version__, "runtime": "python-native"},
        "observationCount": int(prices.shape[0]),
        "allocations": [
            {"symbol": symbol, "weightBps": bps[symbol], "weight": bps[symbol] / 10_000}
            for symbol in symbols
        ],
        **metrics,
        "correlationMatrix": [
            {
                "symbol": symbol,
                "correlations": {
                    other: round(float(correlation[row, column]), 6)
                    for column, other in enumerate(symbols)
                },
            }
            for row, symbol in enumerate(symbols)
        ],
        "frontier": _frontier(mean, covariance, request.max_weight),
        "warnings": [],
    }


__all__ = ["METHODS", "OptimizerInput", "optimize"]
