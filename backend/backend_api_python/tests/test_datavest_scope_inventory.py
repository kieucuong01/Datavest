"""Regression coverage for the static DataVest scope inventory."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from datavest_scope_inventory import _forbidden_match, build_inventory  # noqa: E402


PRESERVED_GROUPS = (
    "market_data",
    "indicator_ide",
    "alerts",
    "backtest",
    "strategy_research",
    "factor_research",
    "ai_analysis",
    "paper_portfolio",
    "free_library",
)

FORBIDDEN_GROUPS = (
    "broker_credentials",
    "live_orders",
    "trading_worker",
    "live_strategy_deploy",
    "agent_trading_scope",
    "grid_copy_trading",
    "billing_credits",
    "paid_hidden_marketplace",
    "mobile",
)

TASK_2B1_GROUPS = (
    "broker_credentials",
    "live_orders",
    "trading_worker",
    "live_strategy_deploy",
    "agent_trading_scope",
    "grid_copy_trading",
)

TASK_2B2_GROUPS = (
    "billing_credits",
    "paid_hidden_marketplace",
)

SYNTHETIC_FORBIDDEN_FIXTURES = (
    (
        "broker_credentials",
        "backend_api_python/app/routes/credentials.py",
        "credentials_blp.route('/list')\n'ibkr'\n'alpaca'\n",
    ),
    (
        "broker_credentials",
        "backend_api_python/app/services/ibkr_trading/client.py",
        "synthetic broker client",
    ),
    (
        "broker_credentials",
        "mcp_server/src/quantdinger_mcp/server.py",
        'GET "/api/agent/v1/trading/accounts"',
    ),
    (
        "live_orders",
        "backend_api_python/app/routes/quick_trade.py",
        "synthetic quick order route",
    ),
    (
        "live_orders",
        "backend_api_python/app/services/live_trading/execution.py",
        "synthetic live execution service",
    ),
    (
        "live_orders",
        "mcp_server/src/quantdinger_mcp/server.py",
        'POST "/api/agent/v1/quick-trade/orders"',
    ),
    (
        "trading_worker",
        "backend_api_python/app/workers/trading.py",
        "synthetic worker",
    ),
    (
        "trading_worker",
        "docker-compose.yml",
        "services:\n  trading-worker:\n    image: synthetic\n",
    ),
    (
        "live_strategy_deploy",
        "backend_api_python/app/routes/strategy.py",
        "strategy_blp.route('/start')\nservice.start_strategy(1)\n",
    ),
    (
        "live_strategy_deploy",
        "backend_api_python/app/services/strategy_runtime/state.py",
        "synthetic strategy runtime",
    ),
    (
        "live_strategy_deploy",
        "mcp_server/src/quantdinger_mcp/server.py",
        'stop_strategy\n/api/agent/v1/strategies/{id}/stop',
    ),
    (
        "agent_trading_scope",
        "backend_api_python/app/utils/agent_auth.py",
        'SCOPE_C = "C"\nSCOPE_T = "T"\ndef agent_required():\n    pass\n',
    ),
    (
        "agent_trading_scope",
        "backend_api_python/app/services/ai_skill_registry.py",
        "T scope requires a live-capable token",
    ),
    (
        "agent_trading_scope",
        "mcp_server/src/quantdinger_mcp/server.py",
        'POST "/api/agent/v1/quick-trade/orders"',
    ),
    (
        "grid_copy_trading",
        "backend_api_python/app/routes/strategy_grid_routes.py",
        "synthetic grid route",
    ),
    (
        "grid_copy_trading",
        "backend_api_python/app/services/grid/engine.py",
        "synthetic grid service",
    ),
    (
        "billing_credits",
        "backend_api_python/app/routes/billing.py",
        "synthetic billing route",
    ),
    (
        "billing_credits",
        "backend_api_python/app/routes/ai_chat.py",
        "from app.services.billing_service import get_billing_service\n",
    ),
    (
        "billing_credits",
        "backend_api_python/app/services/usdt_payment/service.py",
        "synthetic payment service",
    ),
    (
        "paid_hidden_marketplace",
        "backend_api_python/app/services/community_service.py",
        "def purchase_indicator(): pass\npublish_script_template_from_strategy = True\ncode_hidden = True\n",
    ),
    (
        "paid_hidden_marketplace",
        "backend_api_python/app/routes/agent_v1/strategy_sources.py",
        "def _is_hidden_source(item): return item.get(\"code_hidden\")\nraise ValueError('Hidden marketplace source')\n",
    ),
)

SCHEMA_KEYS = (
    "sourceBaselines",
    "trackedSourceFiles",
    "routeModules",
    "runtimeRoles",
    "composeServices",
    "migrationFiles",
    "preservedHits",
    "forbiddenHits",
)


def _route_source_path(module: str) -> str:
    if module.startswith("openapi/"):
        return f"backend_api_python/app/{module}"
    return f"backend_api_python/app/routes/{module}"


def test_inventory_has_exact_safe_schema_and_live_surface_controls():
    """Catch omitted live tools, fabricated routes, and non-path artifact leaves."""
    inventory = build_inventory(REPOSITORY_ROOT)
    tracked = set(inventory["trackedSourceFiles"])

    assert tuple(inventory) == SCHEMA_KEYS
    assert inventory["sourceBaselines"] == {
        "backendTaskBase": "1e350e2c792073351ccaaa82878596c60a89c2bb",
        "backendUpstream": "366ea33c276b5307ce8428da6dcca160532635ea",
        "frontendTaskBase": "6f9ce97fe4730355c39a72610f5dbda3f05d3db7",
        "frontendUpstream": "6f9ce97fe4730355c39a72610f5dbda3f05d3db7",
    }
    assert inventory["trackedSourceFiles"] == sorted(tracked)
    assert all(isinstance(path, str) and not Path(path).is_absolute() and "\\" not in path for path in tracked)
    assert list(inventory["preservedHits"]) == list(PRESERVED_GROUPS)
    assert list(inventory["forbiddenHits"]) == list(FORBIDDEN_GROUPS)
    assert all(isinstance(role, str) for role in inventory["runtimeRoles"])
    assert set(inventory["runtimeRoles"]) == {"api", "celery", "scheduler"}
    assert all(isinstance(name, str) for name in inventory["migrationFiles"])
    assert set(inventory["migrationFiles"]) <= tracked
    assert list(inventory["composeServices"]) == sorted(inventory["composeServices"])
    assert all(path in tracked for path in inventory["composeServices"])
    assert all(
        isinstance(service, str) and service
        for services in inventory["composeServices"].values()
        for service in services
    )
    assert all(_route_source_path(module) in tracked for module in inventory["routeModules"])
    assert "__init__.py" not in inventory["routeModules"]
    assert {
        "openapi/routes/health.py",
        "agent_v1/research.py",
    } <= set(inventory["routeModules"])
    assert {
        "script_source_routes.py",
        "strategy_notifications.py",
        "strategy_review_routes.py",
    } <= set(inventory["routeModules"])
    assert {
        "billing.py",
        "credentials.py",
        "ibkr.py",
        "alpaca.py",
        "quick_trade.py",
        "strategy_account_routes.py",
        "strategy_asset_routes.py",
        "strategy_deviation_routes.py",
        "strategy_executor_routes.py",
        "strategy_grid_routes.py",
        "strategy_ledger_routes.py",
        "strategy_logs_routes.py",
        "strategy_positions_routes.py",
        "strategy_position_ownership_routes.py",
        "agent_v1/quick_trade.py",
        "agent_v1/runtime.py",
        "agent_v1/trading_data.py",
    }.isdisjoint(inventory["routeModules"])

    for groups in (inventory["preservedHits"], inventory["forbiddenHits"]):
        for paths in groups.values():
            assert paths == sorted(paths)
            assert all(isinstance(path, str) and path in tracked for path in paths)

    mcp_server = "mcp_server/src/quantdinger_mcp/server.py"
    assert mcp_server in tracked
    for group in TASK_2B1_GROUPS:
        assert inventory["forbiddenHits"][group] == []
    assert inventory["forbiddenHits"]["mobile"] == []

    for group in TASK_2B2_GROUPS:
        assert inventory["forbiddenHits"][group] == []

    assert "backend_api_python/app/routes/agent_v1/research.py" not in inventory["forbiddenHits"]["agent_trading_scope"]
    assert "backend_api_python/app/services/strategy_review.py" not in inventory["forbiddenHits"]["live_strategy_deploy"]


def test_inventory_uses_only_tracked_source_files():
    """Catch local untracked source changing a supposedly pinned artifact."""
    local_file = REPOSITORY_ROOT / "mcp_server" / "src" / "quantdinger_mcp" / "local_scope_probe.py"
    local_file.write_text('POST "/api/agent/v1/quick-trade/orders"', encoding="utf-8")
    try:
        inventory = build_inventory(REPOSITORY_ROOT)
    finally:
        local_file.unlink()

    assert "mcp_server/src/quantdinger_mcp/local_scope_probe.py" not in inventory["trackedSourceFiles"]
    assert all(
        "mcp_server/src/quantdinger_mcp/local_scope_probe.py" not in paths
        for paths in inventory["forbiddenHits"].values()
    )


@pytest.mark.parametrize(
    ("group", "path", "source"),
    SYNTHETIC_FORBIDDEN_FIXTURES,
)
def test_forbidden_inventory_matchers_keep_synthetic_positive_controls(group, path, source):
    assert _forbidden_match(group, path, source) is True


def test_paid_marketplace_gate_is_empty_after_free_visible_conversion():
    assert build_inventory(REPOSITORY_ROOT)["forbiddenHits"]["paid_hidden_marketplace"] == []


def test_billing_gate_is_empty_after_payment_removal():
    assert build_inventory(REPOSITORY_ROOT)["forbiddenHits"]["billing_credits"] == []


def test_inventory_fails_clearly_without_git_enumeration():
    """Catch a silent filesystem fallback when the source checkout is unavailable."""
    with tempfile.TemporaryDirectory() as checkout:
        with pytest.raises(RuntimeError, match="Unable to enumerate tracked files"):
            build_inventory(Path(checkout))
