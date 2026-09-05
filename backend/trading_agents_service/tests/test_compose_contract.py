"""Static security contract for the private TradingAgents Compose service."""

from __future__ import annotations

from pathlib import Path

import yaml


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class _ComposeLoader(yaml.SafeLoader):
    """Accept Compose's `!override` sequence tag while testing static shape."""


def _construct_override(loader, node):
    return loader.construct_sequence(node)


_ComposeLoader.add_constructor("!override", _construct_override)


def _compose(name: str) -> dict:
    return yaml.load((BACKEND_ROOT / name).read_text(encoding="utf-8"), Loader=_ComposeLoader)


def test_trading_agents_has_no_host_port_and_is_non_root():
    compose = _compose("docker-compose.datavest.yml")
    service = compose["services"]["trading-agents"]

    assert "ports" not in service
    assert service["user"] != "0:0"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["profiles"] == ["trading-agents"]
    assert service["depends_on"]["backend"]["condition"] == "service_healthy"
    assert "trading_agents_state:/var/lib/tradingagents" in service["volumes"]


def test_production_lockdown_and_env_template_enable_private_service_only():
    production = _compose("docker-compose.production.yml")
    service = production["services"]["trading-agents"]
    env_template = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")

    assert service["user"] == "10002:10002"
    assert service["read_only"] is True
    assert "DATAVEST_TRADING_AGENTS_ENABLED" in env_template
    assert "DATAVEST_TRADING_AGENTS_SERVICE_SECRET" in env_template
    assert "DATAVEST_TRADING_AGENTS_CALLBACK_SECRET" in env_template
