"""Canonical market module registry.

This is the first layer of the modular market architecture. Market modules
describe what a market is and which read-only data sources make it useful.
UI visibility still comes from
ENABLED_MARKETS / legacy SHOW_* flags via app.utils.market_visibility.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

from dotenv import dotenv_values

from app.markets.models import DataRequirement, MarketModule
from app.utils.supported_markets import DEFAULT_VISIBLE_MARKETS, SUPPORTED_MARKET_ORDER
MARKET_ORDER = [
    *SUPPORTED_MARKET_ORDER,
]

_RUNTIME_ENV_CACHE: Dict[str, str] = {}
_RUNTIME_ENV_CACHE_UNTIL = 0.0
_RUNTIME_ENV_CACHE_TTL = 5.0


MARKET_MODULES: Dict[str, MarketModule] = {
    "Crypto": MarketModule(
        key="Crypto",
        label="Crypto",
        description="Digital assets and crypto derivatives.",
        asset_class="crypto",
        symbol_hint="BTC/USDT",
        base_currency="USDT",
        features=["research", "backtest", "paper"],
        data_requirements=[
            DataRequirement(
                key="ccxt",
                label="CCXT exchange",
                setting_keys=["CCXT_DEFAULT_EXCHANGE"],
                required=True,
                purpose="quotes and OHLCV",
            ),
            DataRequirement(
                key="coinglass",
                label="Coinglass",
                setting_keys=["COINGLASS_API_KEY"],
                recommended=True,
                purpose="derivatives metrics",
            ),
            DataRequirement(
                key="cryptoquant",
                label="CryptoQuant",
                setting_keys=["CRYPTOQUANT_API_KEY"],
                purpose="on-chain metrics",
            ),
        ],
        supports={"spot": True, "swap": True, "short": True, "session": "24/7"},
    ),
    "USStock": MarketModule(
        key="USStock",
        label="US Stocks",
        description="US equities and ETFs.",
        asset_class="equity",
        symbol_hint="AAPL",
        base_currency="USD",
        features=["research", "backtest", "paper"],
        data_requirements=[
            DataRequirement(
                key="yfinance",
                label="Yahoo Finance fallback",
                built_in=True,
                purpose="basic quotes and OHLCV",
            ),
            DataRequirement(
                key="finnhub",
                label="Finnhub",
                setting_keys=["FINNHUB_API_KEY"],
                recommended=True,
                purpose="quotes, profiles, and news",
            ),
            DataRequirement(
                key="trading_economics",
                label="Trading Economics",
                setting_keys=["TRADING_ECONOMICS_CLIENT", "TRADING_ECONOMICS_KEY"],
                purpose="economic calendar",
            ),
        ],
        supports={"spot": True, "swap": False, "short": False, "session": "exchange-hours"},
    ),
    "VNStock": MarketModule(
        key="VNStock",
        label="Vietnam Stocks",
        description="Vietnamese equities listed on HOSE, HNX, and UPCOM.",
        asset_class="equity",
        symbol_hint="FPT",
        base_currency="VND",
        features=["research", "backtest", "paper"],
        data_requirements=[
            DataRequirement(
                key="kbs_public",
                label="KB Securities public feed",
                built_in=True,
                purpose="quotes and OHLCV",
            ),
        ],
        supports={"spot": True, "swap": False, "short": False, "session": "exchange-hours"},
    ),
    "Forex": MarketModule(
        key="Forex",
        label="Gold (XAU)",
        description="Gold spot data through the XAU provider namespace.",
        asset_class="commodity",
        symbol_hint="XAUUSD",
        base_currency="USD",
        features=["research", "backtest", "paper"],
        data_requirements=[
            DataRequirement(
                key="yfinance",
                label="Yahoo Finance fallback",
                built_in=True,
                purpose="gold quotes and OHLCV",
            ),
            DataRequirement(
                key="twelve_data",
                label="Twelve Data",
                setting_keys=["TWELVE_DATA_API_KEY"],
                recommended=True,
                purpose="gold quotes and K-lines",
            ),
            DataRequirement(
                key="tiingo",
                label="Tiingo",
                setting_keys=["TIINGO_API_KEY"],
                purpose="gold fallback",
            ),
        ],
        supports={"spot": True, "swap": False, "short": False, "session": "24/7"},
    ),
}


def _backend_env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def load_runtime_env() -> Dict[str, str]:
    """Return .env values overlaid with process env values."""
    global _RUNTIME_ENV_CACHE, _RUNTIME_ENV_CACHE_UNTIL
    now = time.monotonic()
    if _RUNTIME_ENV_CACHE and now < _RUNTIME_ENV_CACHE_UNTIL:
        return dict(_RUNTIME_ENV_CACHE)

    values: Dict[str, str] = {}
    path = _backend_env_path()
    if path.exists():
        values.update({k: str(v or "") for k, v in dotenv_values(path).items()})
    values.update({k: str(v) for k, v in os.environ.items()})
    _RUNTIME_ENV_CACHE = dict(values)
    _RUNTIME_ENV_CACHE_UNTIL = now + _RUNTIME_ENV_CACHE_TTL
    return values


def clear_runtime_env_cache() -> None:
    global _RUNTIME_ENV_CACHE, _RUNTIME_ENV_CACHE_UNTIL
    _RUNTIME_ENV_CACHE = {}
    _RUNTIME_ENV_CACHE_UNTIL = 0.0


def list_market_keys() -> List[str]:
    return [key for key in MARKET_ORDER if key in MARKET_MODULES]


def market_options() -> List[Dict[str, str]]:
    return [{"value": key, "label": MARKET_MODULES[key].label} for key in list_market_keys()]


def _setting_configured(env: Mapping[str, str], key: str) -> bool:
    value = env.get(key)
    if value is None:
        value = os.getenv(key, "")
    return str(value or "").strip() != ""


def _flag(env: Mapping[str, str], name: str, default: str) -> bool:
    return str(env.get(name, default) or default).strip().lower() in ("1", "true", "yes", "on")


def _enabled_from_env(env: Mapping[str, str], market: str) -> bool:
    raw = str(env.get("ENABLED_MARKETS", "") or "").strip()
    if raw:
        allowed = {
            part
            for part in (part.strip() for part in raw.split(","))
            if part and part in SUPPORTED_MARKET_ORDER
        }
        return market in allowed
    return market in DEFAULT_VISIBLE_MARKETS


def _requirement_status(req: DataRequirement, env: Mapping[str, str]) -> Dict[str, object]:
    configured = bool(req.built_in)
    if req.setting_keys:
        configured = any(_setting_configured(env, key) for key in req.setting_keys)
    return {
        "key": req.key,
        "label": req.label,
        "setting_keys": list(req.setting_keys),
        "required": req.required,
        "recommended": req.recommended,
        "purpose": req.purpose,
        "built_in": req.built_in,
        "configured": configured,
    }


def _status_for(enabled: bool, requirements: Iterable[Dict[str, object]]) -> str:
    if not enabled:
        return "disabled"
    reqs = list(requirements)
    if any(r.get("required") and not r.get("configured") for r in reqs):
        return "blocked"
    if any(r.get("recommended") and not r.get("configured") for r in reqs):
        return "partial"
    return "ready" if reqs else "partial"


def serialize_market_module(module: MarketModule, env: Optional[Mapping[str, str]] = None) -> Dict[str, object]:
    env_map = env or load_runtime_env()
    enabled = _enabled_from_env(env_map, module.key)
    data_sources = [_requirement_status(req, env_map) for req in module.data_requirements]
    return {
        "key": module.key,
        "label": module.label,
        "description": module.description,
        "asset_class": module.asset_class,
        "symbol_hint": module.symbol_hint,
        "base_currency": module.base_currency,
        "enabled": enabled,
        "features": list(module.features),
        "data_sources": data_sources,
        "supports": dict(module.supports),
        "status": _status_for(enabled, data_sources),
    }


def list_market_modules(env: Optional[Mapping[str, str]] = None) -> List[Dict[str, object]]:
    env_map = env or load_runtime_env()
    return [serialize_market_module(MARKET_MODULES[key], env_map) for key in list_market_keys()]
