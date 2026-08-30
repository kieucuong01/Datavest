"""Low-cardinality metrics for DataVest feature operations."""

from __future__ import annotations

from functools import wraps

from app.observability.metrics import DATAVEST_FEATURE_OUTCOMES, DATAVEST_FEATURE_REQUESTS


_OPERATIONS = frozenset(
    {
        ("smart_insights", "overview"),
        ("smart_insights", "data_health"),
        ("smart_insights", "crypto_market_pulse"),
        ("smart_insights", "live_assets"),
        ("smart_insights", "refresh"),
        ("portfolio_optimizer", "create"),
        ("portfolio_optimizer", "paper_apply"),
    }
)


def _outcome(status: int) -> str:
    if 200 <= status < 400:
        return "success"
    if 400 <= status < 500:
        return "client_error"
    return "server_error"


def _status_code(result) -> int:
    if isinstance(result, tuple) and len(result) >= 2 and isinstance(result[1], int):
        return result[1]
    return int(getattr(result, "status_code", 200))


def observe_feature_operation(feature: str, operation: str):
    """Count one request and its bounded HTTP outcome category."""
    if (feature, operation) not in _OPERATIONS:
        raise ValueError("unsupported_datavest_metric_operation")

    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            DATAVEST_FEATURE_REQUESTS.labels(feature=feature, operation=operation).inc()
            try:
                result = func(*args, **kwargs)
            except Exception:
                DATAVEST_FEATURE_OUTCOMES.labels(
                    feature=feature,
                    operation=operation,
                    outcome="server_error",
                ).inc()
                raise
            DATAVEST_FEATURE_OUTCOMES.labels(
                feature=feature,
                operation=operation,
                outcome=_outcome(_status_code(result)),
            ).inc()
            return result

        return wrapped

    return decorator


__all__ = ["observe_feature_operation"]
