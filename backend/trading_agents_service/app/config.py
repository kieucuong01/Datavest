"""Container-only configuration for the private TradingAgents service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when a required private-service setting is absent or unsafe."""


@dataclass(frozen=True)
class Settings:
    callback_secret: str
    service_secret: str
    callback_url: str
    state_root: PurePosixPath
    upstream_env: Mapping[str, str]
    host: str
    port: int


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} must be configured")
    return value


def _port(environment: Mapping[str, str]) -> int:
    raw = environment.get("DATAVEST_TRADING_AGENTS_PORT", "8080")
    try:
        port = int(raw)
    except ValueError as error:
        raise ConfigurationError("DATAVEST_TRADING_AGENTS_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError("DATAVEST_TRADING_AGENTS_PORT must be between 1 and 65535")
    return port


def _state_root(environment: Mapping[str, str]) -> PurePosixPath:
    root = PurePosixPath(_required(environment, "DATAVEST_TRADING_AGENTS_STATE_ROOT"))
    if not root.is_absolute():
        raise ConfigurationError("DATAVEST_TRADING_AGENTS_STATE_ROOT must be an absolute path")
    if ".." in root.parts:
        raise ConfigurationError("DATAVEST_TRADING_AGENTS_STATE_ROOT must not contain '..'")
    return root


def _callback_url(environment: Mapping[str, str]) -> str:
    value = _required(environment, "DATAVEST_TRADING_AGENTS_CALLBACK_URL")
    if not value.startswith(("http://", "https://")) or "@" in value:
        raise ConfigurationError("DATAVEST_TRADING_AGENTS_CALLBACK_URL must be an internal HTTP URL")
    return value


def _upstream_environment(environment: Mapping[str, str]) -> Mapping[str, str]:
    """Forward native upstream and DeepSeek environment keys without mutation."""

    return MappingProxyType(
        {
            key: value
            for key, value in environment.items()
            if key.startswith("TRADINGAGENTS_") or key.startswith("DEEPSEEK_")
        }
    )


def load_settings(environment: Mapping[str, str] | None = None) -> Settings:
    """Load service settings without importing TradingAgents or logging secrets."""

    source = os.environ if environment is None else environment
    return Settings(
        callback_secret=_required(source, "DATAVEST_TRADING_AGENTS_CALLBACK_SECRET"),
        service_secret=_required(source, "DATAVEST_TRADING_AGENTS_SERVICE_SECRET"),
        callback_url=_callback_url(source),
        state_root=_state_root(source),
        upstream_env=_upstream_environment(source),
        host=source.get("DATAVEST_TRADING_AGENTS_HOST", "0.0.0.0"),
        port=_port(source),
    )
