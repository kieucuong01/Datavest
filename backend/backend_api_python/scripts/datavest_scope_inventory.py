"""Create a deterministic, tracked-source inventory for the DataVest fork boundary."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path


SOURCE_BASELINES = {
    "backendTaskBase": "1e350e2c792073351ccaaa82878596c60a89c2bb",
    "backendUpstream": "366ea33c276b5307ce8428da6dcca160532635ea",
    "frontendTaskBase": "6f9ce97fe4730355c39a72610f5dbda3f05d3db7",
    "frontendUpstream": "6f9ce97fe4730355c39a72610f5dbda3f05d3db7",
}

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

MCP_SERVER = "mcp_server/src/quantdinger_mcp/server.py"


def _tracked_files(repository_root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Unable to enumerate tracked files with git ls-files") from error
    return sorted(
        path
        for path in completed.stdout.decode("utf-8").split("\0")
        if path and (repository_root / path).is_file()
    )


def _inventory_source_files(tracked_files: list[str]) -> list[str]:
    return [
        path
        for path in tracked_files
        if (
            path.startswith("backend_api_python/app/") and path.endswith(".py")
        )
        or (path.startswith("backend_api_python/migrations/") and path.endswith(".sql"))
        or (path.startswith("mcp_server/src/quantdinger_mcp/") and path.endswith(".py"))
        or (path.startswith("docker-compose") and path.endswith((".yml", ".yaml")))
    ]


def _read_source(repository_root: Path, relative_path: str) -> str:
    return (repository_root / relative_path).read_text(encoding="utf-8", errors="replace")


def _under(path: str, *prefixes: str) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _has_all(source: str, *contracts: str) -> bool:
    return all(contract in source for contract in contracts)


def _preserved_match(group: str, path: str, source: str) -> bool:
    del source
    rules = {
        "market_data": lambda: path in {
            "backend_api_python/app/routes/market.py",
            "backend_api_python/app/routes/kline.py",
            "backend_api_python/app/routes/global_market.py",
            "backend_api_python/app/routes/universe.py",
            "backend_api_python/app/services/strategy_v2/market_data.py",
        } or _under(path, "backend_api_python/app/services/market/"),
        "indicator_ide": lambda: path in {
            "backend_api_python/app/routes/indicator.py",
            "backend_api_python/app/routes/indicator_signal_alerts.py",
        } or _under(path, "backend_api_python/app/services/indicator/"),
        "alerts": lambda: path in {
            "backend_api_python/app/routes/indicator_signal_alerts.py",
            "backend_api_python/app/routes/strategy_notifications.py",
            "backend_api_python/app/services/notification_display.py",
        },
        "backtest": lambda: path in {
            "backend_api_python/app/routes/backtest_center.py",
            "backend_api_python/app/routes/agent_v1/backtests.py",
        } or _under(path, "backend_api_python/app/services/backtest/"),
        "strategy_research": lambda: path in {
            "backend_api_python/app/routes/agent_v1/research.py",
            "backend_api_python/app/routes/script_source_routes.py",
            "backend_api_python/app/services/strategy_review.py",
        } or _under(path, "backend_api_python/app/services/strategy_v2/"),
        "factor_research": lambda: path in {
            "backend_api_python/app/routes/factors.py",
            "backend_api_python/app/services/strategy_v2/factor_research.py",
        },
        "ai_analysis": lambda: path in {
            "backend_api_python/app/routes/ai_chat.py",
            "backend_api_python/app/routes/fast_analysis.py",
        } or _under(path, "backend_api_python/app/services/ai_"),
        "paper_portfolio": lambda: path in {
            "backend_api_python/app/routes/portfolio.py",
            "backend_api_python/app/routes/agent_v1/portfolio.py",
        } or _under(path, "backend_api_python/app/services/portfolio/"),
        "free_library": lambda: path in {
            "backend_api_python/app/routes/community.py",
            "backend_api_python/app/routes/universe.py",
        } or _under(path, "backend_api_python/app/services/universe"),
    }
    return rules[group]()


def _forbidden_match(group: str, path: str, source: str) -> bool:
    mcp_quick_order = path == MCP_SERVER and "/api/agent/v1/quick-trade/orders" in source
    mcp_broker_accounts = path == MCP_SERVER and "/api/agent/v1/trading/accounts" in source
    broker_contract = (
        (path == "backend_api_python/app/routes/credentials.py" and _has_all(source, "credentials_blp.route", "'ibkr'", "'alpaca'"))
        or (path == "backend_api_python/app/routes/ibkr.py" and _has_all(source, "ibkr_blp.route('/connect'", "ibkr_blp.route('/order'"))
        or (path == "backend_api_python/app/routes/alpaca.py" and _has_all(source, "alpaca_blp.route('/connect'", "alpaca_blp.route('/order'"))
        or (path == "backend_api_python/app/services/quick_trade/credentials.py" and "credential" in source)
        or (path == "backend_api_python/app/utils/broker_session.py" and "BrokerSessionRegistry" in source)
        or _under(
            path,
            "backend_api_python/app/services/ibkr_trading/",
            "backend_api_python/app/services/alpaca_trading/",
        )
        or (path == "backend_api_python/app/services/live_trading/factory.py" and _has_all(source, "create_ibkr_client", "create_alpaca_client"))
        or mcp_broker_accounts
    )
    registered_strategy_control = (
        _under(path, "backend_api_python/app/routes/")
        and re.search(
            r"\.route\([^\n]*(?:/start|/stop|system-strategies/toggle)",
            source,
        ) is not None
        and re.search(r"\.(?:start_strategy|stop_strategy|stop_strategy_with_policy)\(", source) is not None
    )
    agent_strategy_tool = (
        path in {"backend_api_python/app/services/ai_tool_registry.py", MCP_SERVER}
        and _has_all(source, "stop_strategy", "/api/agent/v1/strategies/", "/stop")
    )
    live_strategy_contract = (
        registered_strategy_control
        or agent_strategy_tool
        or (path == "backend_api_python/app/routes/strategy_executor_routes.py" and _has_all(source, 'strategy_blp.route("/strategies/executors/create"', "build_executor_strategy_payload"))
        or (path == "backend_api_python/app/services/trading_executor.py" and _has_all(source, "def start_strategy", "def stop_strategy"))
        or (path == "backend_api_python/app/services/strategy_lifecycle.py" and "auto_stop_live_strategy" in source)
        or _under(path, "backend_api_python/app/services/strategy_runtime/")
        or path in {
            "backend_api_python/app/services/strategy_command_client.py",
            "backend_api_python/app/services/strategy_command_repository.py",
            "backend_api_python/app/services/strategy_v2/deployment.py",
            "backend_api_python/app/services/strategy_v2/live_execution.py",
            "backend_api_python/app/services/strategy_live_guard.py",
        }
    )
    agent_scope_contract = (
        (path == "backend_api_python/app/utils/agent_auth.py" and _has_all(source, 'SCOPE_C = "C"', 'SCOPE_T = "T"', "def agent_required"))
        or (path == "backend_api_python/app/services/agent_token_service.py" and _has_all(source, "SCOPE_C", "allow_c_scope", "paper_only"))
        or (path == "backend_api_python/app/routes/agent_v1/admin.py" and "allow_c_scope=True" in source)
        or (path == "backend_api_python/app/routes/agent_v1/me_tokens.py" and "allow_c_scope=False" in source)
        or (path == "backend_api_python/app/routes/agent_v1/quick_trade.py" and _has_all(source, "SCOPE_T", 'route("/quick-trade/orders"'))
        or (path == "backend_api_python/app/routes/agent_v1/runtime.py" and "SCOPE_T" in source)
        or (path == "backend_api_python/app/routes/agent_v1/trading_data.py" and 'route("/trading/accounts"' in source)
        or (path == "backend_api_python/app/services/ai_tool_registry.py" and _has_all(source, 'route="/api/agent/v1/quick-trade/orders"', '"list_trading_accounts"'))
        or (path == "backend_api_python/app/services/ai_skill_registry.py" and _has_all(source, "T scope", "live-capable token"))
        or mcp_quick_order
        or mcp_broker_accounts
    )
    billing_hook = (
        _under(path, "backend_api_python/app/routes/", "backend_api_python/app/services/")
        and "app.services.billing_service" in source
    )
    usdt_payment_compatibility = (
        path == "backend_api_python/app/services/usdt_payment_service.py"
        and _has_all(
            source,
            "from app.services.usdt_payment.service import",
            "get_usdt_payment_service",
            "get_usdt_order_worker",
        )
    )
    usdt_payment_consumer = (
        re.search(
            r"^\s*from app\.services\.usdt_payment_service import ",
            source,
            re.MULTILINE,
        ) is not None
    )
    paid_marketplace_dependency = (
        "from app.services.community_service import get_community_service" in source
        or "from app.services.strategy_assets import get_strategy_asset_service" in source
    )
    paid_marketplace_contract = (
        _under(path, "backend_api_python/app/routes/", "backend_api_python/app/services/")
        and (
            paid_marketplace_dependency
            or _has_all(source, "def purchase_indicator", "publish_script_template_from_strategy", "code_hidden")
            or _has_all(source, "publish_to_community", "pricing_type", "code_hidden")
            or _has_all(source, "create_from_marketplace_asset", "source_marketplace_indicator_id", "code_hidden")
            or _has_all(source, "source_marketplace_indicator_id", '"is_purchased"', '"code_hidden"')
            or (
                _under(path, "backend_api_python/app/routes/agent_v1/")
                and _has_all(source, "def _is_hidden_source", 'item.get("code_hidden")', "Hidden marketplace source")
            )
        )
    )
    rules = {
        "broker_credentials": lambda: broker_contract,
        "live_orders": lambda: path in {
            "backend_api_python/app/routes/quick_trade.py",
            "backend_api_python/app/routes/agent_v1/quick_trade.py",
            "backend_api_python/app/services/quick_trade/orders.py",
        } or _under(path, "backend_api_python/app/services/live_trading/") or mcp_quick_order,
        "trading_worker": lambda: path == "backend_api_python/app/workers/trading.py" or (
            path.startswith("docker-compose") and re.search(r"^  trading-worker:", source, re.MULTILINE) is not None
        ),
        "live_strategy_deploy": lambda: live_strategy_contract,
        "agent_trading_scope": lambda: agent_scope_contract,
        "grid_copy_trading": lambda: path == "backend_api_python/app/routes/strategy_grid_routes.py" or _under(
            path,
            "backend_api_python/app/services/grid/",
            "backend_api_python/app/services/live_trading/grid_",
        ),
        "billing_credits": lambda: path in {
            "backend_api_python/app/routes/billing.py",
            "backend_api_python/app/services/billing_config.py",
            "backend_api_python/app/services/billing_service.py",
        } or _under(path, "backend_api_python/app/services/usdt_payment/") or billing_hook or usdt_payment_compatibility or usdt_payment_consumer,
        "paid_hidden_marketplace": lambda: paid_marketplace_contract,
        "mobile": lambda: path.startswith("docker-compose") and re.search(r"^  mobile:", source, re.MULTILINE) is not None,
    }
    return rules[group]()


def _hit_groups(repository_root: Path, source_files: list[str], groups: tuple[str, ...], matcher) -> dict[str, list[str]]:
    sources = {path: _read_source(repository_root, path) for path in source_files}
    return {
        group: [path for path, source in sources.items() if matcher(group, path, source)]
        for group in groups
    }


def _registered_route_modules(repository_root: Path, tracked_files: set[str]) -> list[str]:
    backend_root = repository_root / "backend_api_python" / "app"
    modules: set[str] = set()
    openapi_tree = ast.parse((backend_root / "openapi" / "register.py").read_text(encoding="utf-8"))
    route_queue: list[str] = []
    for node in ast.walk(openapi_tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.module.startswith("app.openapi.routes."):
            name = node.module.removeprefix("app.openapi.routes.")
            modules.add(f"openapi/routes/{name}.py")
        elif node.module.startswith("app.routes."):
            name = node.module.removeprefix("app.routes.")
            candidate = f"backend_api_python/app/routes/{name}.py"
            if candidate in tracked_files:
                modules.add(f"{name}.py")
                route_queue.append(candidate)

    visited: set[str] = set()
    while route_queue:
        relative_path = route_queue.pop()
        if relative_path in visited:
            continue
        visited.add(relative_path)
        route_tree = ast.parse((repository_root / relative_path).read_text(encoding="utf-8"))
        for node in ast.walk(route_tree):
            imported_modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module == "app.routes":
                imported_modules.extend(imported.name for imported in node.names)
            elif isinstance(node, ast.Import):
                imported_modules.extend(
                    imported.name.removeprefix("app.routes.")
                    for imported in node.names
                    if imported.name.startswith("app.routes.")
                )
            for name in imported_modules:
                candidate = f"backend_api_python/app/routes/{name.replace('.', '/')}.py"
                if candidate in tracked_files:
                    normalized = candidate.removeprefix("backend_api_python/app/routes/")
                    modules.add(normalized)
                    route_queue.append(candidate)

    agent_tree = ast.parse((backend_root / "routes" / "agent_v1" / "__init__.py").read_text(encoding="utf-8"))
    for node in ast.walk(agent_tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            for imported in node.names:
                candidate = f"backend_api_python/app/routes/agent_v1/{imported.name}.py"
                if candidate in tracked_files:
                    modules.add(f"agent_v1/{imported.name}.py")
    return sorted(modules)


def _runtime_roles(repository_root: Path) -> list[str]:
    roles_path = repository_root / "backend_api_python" / "app" / "runtime" / "roles.py"
    tree = ast.parse(roles_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ProcessRole":
            return sorted(
                assignment.value.value
                for assignment in node.body
                if isinstance(assignment, ast.Assign)
                and isinstance(assignment.value, ast.Constant)
                and isinstance(assignment.value.value, str)
            )
    return []


def _compose_services(repository_root: Path, compose_files: list[str]) -> dict[str, list[str]]:
    inventories: dict[str, list[str]] = {}
    for relative_path in compose_files:
        in_services = False
        services: list[str] = []
        for line in _read_source(repository_root, relative_path).splitlines():
            if line == "services:":
                in_services = True
                continue
            if in_services and line and not line[0].isspace():
                break
            if in_services:
                match = re.match(r"^  ([A-Za-z0-9_-]+):", line)
                if match:
                    services.append(match.group(1))
        inventories[relative_path] = sorted(set(services))
    return inventories


def build_inventory(repository_root: Path) -> dict[str, object]:
    """Return a source-only, JSON-safe inventory for the pinned backend tree."""
    repository_root = repository_root.resolve()
    tracked_files = _tracked_files(repository_root)
    source_files = _inventory_source_files(tracked_files)
    tracked_set = set(tracked_files)
    compose_files = [path for path in source_files if path.startswith("docker-compose")]
    return {
        "sourceBaselines": dict(SOURCE_BASELINES),
        "trackedSourceFiles": source_files,
        "routeModules": _registered_route_modules(repository_root, tracked_set),
        "runtimeRoles": _runtime_roles(repository_root),
        "composeServices": _compose_services(repository_root, compose_files),
        "migrationFiles": [path for path in source_files if path.startswith("backend_api_python/migrations/")],
        "preservedHits": _hit_groups(repository_root, source_files, PRESERVED_GROUPS, _preserved_match),
        "forbiddenHits": _hit_groups(repository_root, source_files, FORBIDDEN_GROUPS, _forbidden_match),
    }


def main() -> int:
    repository_root = Path(__file__).resolve().parents[2]
    json.dump(build_inventory(repository_root), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
