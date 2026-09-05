from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import ConfigurationError, load_settings


def _set_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATAVEST_TRADING_AGENTS_CALLBACK_SECRET", "test-callback-secret")
    monkeypatch.setenv("DATAVEST_TRADING_AGENTS_STATE_ROOT", "/var/lib/tradingagents")


def test_service_rejects_missing_callback_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATAVEST_TRADING_AGENTS_CALLBACK_SECRET", raising=False)
    monkeypatch.setenv("DATAVEST_TRADING_AGENTS_STATE_ROOT", "/var/lib/tradingagents")

    with pytest.raises(ConfigurationError, match="DATAVEST_TRADING_AGENTS_CALLBACK_SECRET"):
        load_settings()


def test_service_preserves_upstream_provider_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("TRADINGAGENTS_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "not-a-real-key")

    settings = load_settings()

    assert settings.upstream_env["TRADINGAGENTS_LLM_PROVIDER"] == "deepseek"
    assert settings.upstream_env["DEEPSEEK_API_KEY"] == "not-a-real-key"
    assert settings.state_root == PurePosixPath("/var/lib/tradingagents")


def test_service_rejects_relative_state_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATAVEST_TRADING_AGENTS_CALLBACK_SECRET", "test-callback-secret")
    monkeypatch.setenv("DATAVEST_TRADING_AGENTS_STATE_ROOT", "state")

    with pytest.raises(ConfigurationError, match="absolute"):
        load_settings()
