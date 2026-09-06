from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar

import tradingagents.default_config as default_config

# Use default config but allow it to be overridden
_config: dict | None = None
_run_config: ContextVar[dict | None] = ContextVar("tradingagents_run_config", default=None)


@contextmanager
def isolated_config():
    """Isolate language, providers and cache paths for one hosted graph run."""
    token = _run_config.set(deepcopy(default_config.DEFAULT_CONFIG))
    try:
        yield
    finally:
        _run_config.reset(token)


def initialize_config():
    """Initialize the configuration with default values."""
    global _config
    if _config is None:
        _config = deepcopy(default_config.DEFAULT_CONFIG)


def set_config(config: dict):
    """Update the configuration with custom values.

    Dict-valued keys (e.g. ``data_vendors``) are merged one level deep so a
    partial update like ``{"data_vendors": {"core_stock_apis": "alpha_vantage"}}``
    keeps the other nested keys from the default; scalar keys are replaced.
    """
    global _config
    initialize_config()
    target = deepcopy(_run_config.get() if _run_config.get() is not None else _config)
    incoming = deepcopy(config)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key].update(value)
        else:
            target[key] = value
    if _run_config.get() is not None:
        _run_config.set(target)
    else:
        _config = target


def get_config() -> dict:
    """Get the current configuration."""
    if _config is None:
        initialize_config()
    return deepcopy(_run_config.get() if _run_config.get() is not None else _config)


# Initialize with default config
initialize_config()
