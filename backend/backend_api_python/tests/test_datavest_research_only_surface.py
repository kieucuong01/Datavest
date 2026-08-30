"""Behavior contracts for the DataVest research-and-paper-only boundary."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml
from flask import Flask

from app.runtime.roles import ProcessRole, current_process_role
from app.services.agent_token_service import TokenIssueError, _parse_issue_body, get_token_policy
from app.utils import agent_auth, auth as core_auth


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent

FORBIDDEN_PREFIXES = (
    "/api/credentials",
    "/api/ibkr",
    "/api/alpaca",
    "/api/billing",
    "/api/quick-trade",
    "/api/strategy-assets",
    "/api/agent/v1/quick-trade",
    "/api/agent/v1/trading",
    "/api/agent/v1/runtime",
)

FORBIDDEN_EXACT_PATHS = {
    "/api/community/indicators/{indicator_id}/purchase",
    "/api/community/indicators/{indicator_id}/sync",
    "/api/community/my-purchases",
    "/api/community/author/summary",
    "/api/community/author/sales",
    "/api/users/set-credits",
    "/api/users/set-vip",
    "/api/users/credits-log",
    "/api/users/my-credits-log",
    "/api/users/my-referrals",
    "/api/users/system-strategies",
    "/api/users/system-strategies/toggle",
    "/api/users/system-strategies/delete",
    "/api/users/admin-orders",
    "/api/users/admin-orders/{order_id}/manual-confirm",
    "/api/dashboard/pendingOrders",
    "/api/dashboard/pendingOrders/{order_id}",
    "/api/strategies/{strategy_id}/start",
    "/api/strategies/{strategy_id}/stop",
    "/api/strategies/exchange/test",
    "/api/agent/v1/strategies/{strategy_id}/stop",
}

FORBIDDEN_STRATEGY_PREFIXES = (
    "/api/account/",
    "/api/strategies/executors",
    "/api/strategies/grid-",
    "/api/strategies/dry-run-deviation",
    "/api/strategies/position-ownership",
    "/api/strategies/positions",
    "/api/strategies/trades",
)

PRESERVED_PREFIXES = {
    "market": "/api/market",
    "indicator": "/api/indicator",
    "backtest": "/api/backtest",
    "factors": "/api/factors",
    "ai": "/api/ai",
    "portfolio": "/api/portfolio",
    "community": "/api/community",
    "agent_market": "/api/agent/v1/markets",
    "agent_indicator": "/api/agent/v1/indicators",
    "agent_backtest": "/api/agent/v1/backtest",
    "agent_research": "/api/agent/v1/research",
    "agent_portfolio": "/api/agent/v1/portfolio",
}


def _normalize_rule(rule: str) -> str:
    import re

    return re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", rule)


def _is_forbidden_path(path: str) -> bool:
    normalized = _normalize_rule(path)
    return (
        normalized.startswith(FORBIDDEN_PREFIXES)
        or normalized in FORBIDDEN_EXACT_PATHS
        or normalized.startswith(FORBIDDEN_STRATEGY_PREFIXES)
    )


def _registered_paths(app) -> set[str]:
    return {
        _normalize_rule(rule.rule)
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/api/")
    }


def _runtime_openapi_paths(app) -> set[str]:
    from app.openapi import get_openapi_api
    from app.openapi.register import enrich_spec

    api = get_openapi_api(app)
    assert api is not None
    with app.app_context():
        return set(enrich_spec(api.spec.to_dict()).get("paths", {}))


def _documented_paths(relative_path: str) -> set[str]:
    target = REPOSITORY_ROOT / relative_path
    if target.suffix == ".json":
        document = json.loads(target.read_text(encoding="utf-8"))
    else:
        document = yaml.safe_load(target.read_text(encoding="utf-8"))
    return set((document or {}).get("paths", {}))


def test_registered_and_exported_http_surfaces_exclude_forbidden_paths(app):
    path_sets = {
        "registered": _registered_paths(app),
        "runtime human OpenAPI": _runtime_openapi_paths(app),
        "exported human OpenAPI": _documented_paths("docs/api/openapi.yaml"),
        "exported Agent OpenAPI": _documented_paths("docs/agent/agent-openapi.json"),
    }

    for label, paths in path_sets.items():
        forbidden = sorted(path for path in paths if _is_forbidden_path(path))
        assert forbidden == [], f"{label} still exposes forbidden paths: {forbidden}"


def test_representative_removed_routes_are_true_404s(client):
    requests = (
        ("GET", "/api/credentials/list"),
        ("GET", "/api/ibkr/accounts"),
        ("POST", "/api/quick-trade/place-order"),
        ("GET", "/api/community/my-purchases"),
        ("POST", "/api/users/set-credits"),
        ("GET", "/api/dashboard/pendingOrders"),
        ("DELETE", "/api/dashboard/pendingOrders/1"),
        ("POST", "/api/strategies/1/start"),
        ("GET", "/api/agent/v1/runtime/overview"),
        ("POST", "/api/agent/v1/quick-trade/orders"),
        ("GET", "/api/agent/v1/trading/accounts"),
    )

    for method, path in requests:
        response = client.open(path, method=method, json={})
        assert response.status_code == 404, (method, path, response.status_code)


def test_preserved_research_and_paper_routes_remain_registered(app):
    paths = _registered_paths(app)
    for label, prefix in PRESERVED_PREFIXES.items():
        assert any(path == prefix or path.startswith(prefix + "/") for path in paths), label
    assert "/api/community/indicators/{indicator_id}/fork" in paths
    assert "/api/strategies/script-sources" in paths
    assert "/api/strategies/verify" in paths
    assert "/api/strategies/generate" in paths
    assert "/api/dashboard/summary" in paths


def test_process_roles_are_explicit_and_trading_is_rejected(monkeypatch):
    assert {role.value for role in ProcessRole} == {"api", "scheduler", "celery"}
    monkeypatch.setenv("QD_PROCESS_ROLE", "trading")
    with pytest.raises(RuntimeError, match="Invalid QD_PROCESS_ROLE='trading'"):
        current_process_role()


def test_trading_entrypoint_and_startup_hooks_are_unavailable():
    import importlib.util
    from app import startup

    assert importlib.util.find_spec("app.commands.trading_worker") is None
    for name in (
        "get_trading_executor",
        "get_pending_order_worker",
        "get_execution_stream_supervisor",
        "start_pending_order_worker",
        "start_execution_stream_supervisor",
        "start_grid_fill_poller",
        "start_usdt_order_worker",
        "restore_running_strategies",
        "_start_trading_support_services",
    ):
        assert not hasattr(startup, name), name


def test_scheduler_still_starts_research_services_without_payment_worker(monkeypatch):
    from app import startup
    from app.services import ai_calibration, indicator_signal_alerts, market_catalog_sync, reflection

    called: list[str] = []
    monkeypatch.setattr(startup, "start_portfolio_monitor", lambda: called.append("portfolio"))
    monkeypatch.setattr(
        startup,
        "start_usdt_order_worker",
        lambda: pytest.fail("payment worker was started"),
        raising=False,
    )
    monkeypatch.setattr(
        indicator_signal_alerts,
        "start_indicator_signal_alert_worker",
        lambda: called.append("indicator-alerts"),
    )
    monkeypatch.setattr(
        market_catalog_sync,
        "start_market_catalog_sync_on_boot",
        lambda: called.append("market-catalog"),
    )
    monkeypatch.setattr(
        ai_calibration,
        "start_ai_calibration_worker",
        lambda: called.append("ai-calibration"),
    )
    monkeypatch.setattr(
        reflection,
        "start_reflection_worker",
        lambda: called.append("reflection"),
    )

    startup._start_scheduler_services(include_celery_managed=True)

    assert called == [
        "portfolio",
        "indicator-alerts",
        "market-catalog",
        "ai-calibration",
        "reflection",
    ]


@pytest.mark.parametrize("forbidden_scope", ["T", "C"])
def test_agent_token_issuance_rejects_removed_scopes(forbidden_scope):
    with pytest.raises(TokenIssueError, match="Unknown scope"):
        _parse_issue_body({"name": "research-agent", "scopes": ["R", forbidden_scope]})


def test_agent_scope_validation_and_policy_keep_only_safe_scopes():
    assert agent_auth.ALL_SCOPES == ("R", "W", "B", "N")
    assert agent_auth.parse_scopes("R,W,B,N,T,C") == {"R", "W", "B", "N"}
    assert get_token_policy(for_admin=False)["allowed_scopes"] == ["B", "N", "R", "W"]
    assert get_token_policy(for_admin=True)["allowed_scopes"] == ["B", "N", "R", "W"]
    parsed = _parse_issue_body({"name": "research-agent", "scopes": "R,B"})
    assert parsed["scopes"] == {"R", "B"}


def _compose_services(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded.get("services") or {}


def _service_process_roles(services: dict) -> set[str]:
    roles: set[str] = set()
    for service in services.values():
        environment = (service or {}).get("environment") or {}
        if isinstance(environment, list):
            for item in environment:
                if isinstance(item, str) and item.startswith("QD_PROCESS_ROLE="):
                    roles.add(item.split("=", 1)[1])
        elif isinstance(environment, dict) and environment.get("QD_PROCESS_ROLE"):
            roles.add(str(environment["QD_PROCESS_ROLE"]))
    return roles


def test_compose_product_wiring_is_research_only():
    compose_files = sorted(REPOSITORY_ROOT.glob("docker-compose*.yml"))
    assert compose_files
    service_sets = {path.name: set(_compose_services(path)) for path in compose_files}

    for name, services in service_sets.items():
        assert "trading-worker" not in services, name
        assert "mobile" not in services, name

    base_services = service_sets["docker-compose.yml"]
    assert "mcp" not in base_services
    assert {
        "postgres",
        "redis",
        "redis-jobs",
        "backend",
        "frontend",
        "scheduler-worker",
        "celery-worker",
        "celery-beat",
    } <= base_services

    effective_production = base_services | service_sets["docker-compose.production.yml"]
    assert "mcp" not in effective_production
    assert {"redis", "redis-jobs", "scheduler-worker", "celery-worker", "celery-beat"} <= effective_production

    for path in compose_files:
        if path.name == "docker-compose.observability.yml":
            continue
        assert _service_process_roles(_compose_services(path)) <= {"api", "scheduler", "celery"}, path.name


def test_default_cors_origins_are_web_only(monkeypatch):
    import app as app_module

    captured = {}
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.setattr(
        app_module,
        "CORS",
        lambda _app, **kwargs: captured.update(kwargs),
    )

    app_module._configure_cors(Flask(__name__))

    assert captured["origins"] == ["http://localhost:8888", "http://localhost:8000"]
    assert not any("capacitor" in origin or "ionic" in origin or "*" in origin for origin in captured["origins"])


def test_compose_backend_frontend_urls_exclude_removed_mobile_origin():
    for name in ("docker-compose.yml", "docker-compose.ghcr.yml"):
        services = _compose_services(REPOSITORY_ROOT / name)
        environment = services["backend"].get("environment") or {}
        if isinstance(environment, list):
            frontend_url = next(
                item.split("=", 1)[1]
                for item in environment
                if isinstance(item, str) and item.startswith("FRONTEND_URL=")
            )
        else:
            frontend_url = str(environment["FRONTEND_URL"])

        assert "http://localhost:8888" in frontend_url, name
        assert "8889" not in frontend_url, name
        assert "mobile" not in frontend_url.lower(), name


def _mcp_tree() -> ast.Module:
    source = (REPOSITORY_ROOT / "mcp_server/src/quantdinger_mcp/server.py").read_text(encoding="utf-8")
    return ast.parse(source)


def _mcp_declared_tool_names(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "MCP_TOOL_NAMES"
            for target in node.targets
        ):
            return set(ast.literal_eval(node.value))
    raise AssertionError("MCP_TOOL_NAMES is missing")


def _mcp_decorated_tool_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "mcp"
                and decorator.func.attr == "tool"
            ):
                names.add(node.name)
    return names


def _mcp_instructions(tree: ast.Module) -> str:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "mcp" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        for keyword in node.value.keywords:
            if keyword.arg == "instructions":
                return str(ast.literal_eval(keyword.value))
    raise AssertionError("FastMCP instructions are missing")


def test_mcp_registers_only_research_backtest_and_paper_safe_tools():
    tree = _mcp_tree()
    declared = _mcp_declared_tool_names(tree)
    decorated = _mcp_decorated_tool_names(tree)
    assert declared == decorated

    forbidden = {
        "list_strategies",
        "get_strategy",
        "runtime_overview",
        "stop_strategy",
        "place_quick_order",
        "emergency_stop_trading",
        "create_strategy",
        "update_strategy",
        "cancel_open_paper_orders",
        "list_trading_accounts",
        "get_account_snapshot",
        "list_account_positions",
        "list_strategy_positions",
        "list_strategy_trades",
        "list_strategy_pending_orders",
        "list_agent_quick_trades",
    }
    assert declared.isdisjoint(forbidden)
    assert {
        "get_klines",
        "compile_strategy_code",
        "submit_backtest",
        "list_portfolio_positions",
        "list_paper_orders",
        "list_factors",
        "list_watchlist",
    } <= declared

    instructions = _mcp_instructions(tree).lower()
    for phrase in ("live order", "stop_strategy", "credential", "broker account"):
        assert phrase not in instructions


def _authenticate_human(monkeypatch, *, user_id: int = 7, role: str = "user") -> dict[str, str]:
    monkeypatch.setattr(
        core_auth,
        "verify_token",
        lambda _raw: {
            "sub": "researcher",
            "user_id": user_id,
            "role": role,
            "_verified_username": "researcher",
            "_verified_user_role": role,
        },
    )
    return {"Authorization": "Bearer research-jwt"}


def test_community_listing_and_detail_use_free_visible_contract(client, monkeypatch):
    from app.routes import community as community_routes

    captured = {}

    class CommunityService:
        def get_market_indicators(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "total": 0}

        def get_indicator_detail(self, indicator_id, **_kwargs):
            return {"id": indicator_id, "code": "visible source", "source_visible": True}

    monkeypatch.setattr(community_routes, "get_community_service", lambda: CommunityService())
    headers = _authenticate_human(monkeypatch)

    listing = client.get(
        "/api/community/indicators?pricing_type=paid&code_visibility=hidden",
        headers=headers,
    )
    assert listing.status_code == 200
    assert "pricing_type" not in captured
    assert "code_visibility" not in captured

    assert client.get("/api/community/indicators/1", headers=headers).status_code == 200
    second = client.get("/api/community/indicators/2", headers=headers)
    assert second.status_code == 200
    assert second.get_json()["data"]["code"] == "visible source"


def test_free_community_fork_remains_reachable(client, monkeypatch):
    from app.routes import community as community_routes

    class CommunityService:
        def fork_free_indicator(self, *, buyer_id, indicator_id):
            assert buyer_id == 7
            assert indicator_id == 11
            return True, "forked", {"local_copy_id": 22}

    monkeypatch.setattr(community_routes, "get_community_service", lambda: CommunityService())
    response = client.post(
        "/api/community/indicators/11/fork",
        headers=_authenticate_human(monkeypatch),
    )
    assert response.status_code == 200
    assert response.get_json()["data"] == {"local_copy_id": 22}


@pytest.mark.parametrize(
    "payload",
    [
        {"pricingType": "paid", "price": 10},
        {"pricingType": "free", "price": 1},
        {"pricingType": "free", "price": 0, "codeHidden": True},
    ],
)
def test_indicator_publication_rejects_paid_or_hidden_payload_before_persistence(
    client, monkeypatch, payload
):
    from app.routes import indicator as indicator_routes

    monkeypatch.setattr(
        indicator_routes,
        "get_db_connection",
        lambda: pytest.fail("publication reached persistence"),
    )
    response = client.post(
        "/api/indicator/saveIndicator",
        headers=_authenticate_human(monkeypatch),
        json={
            "name": "Free research indicator",
            "code": "def calculate(df, params):\n    return {'plots': [], 'signals': []}\n",
            "publishToCommunity": True,
            **payload,
        },
    )
    assert response.status_code == 400
    assert response.get_json()["msg"] == "community_publication_must_be_free_and_visible"


def test_script_publication_rejects_paid_payload_before_source_lookup(client, monkeypatch):
    from app.routes import script_source_routes

    monkeypatch.setattr(
        script_source_routes,
        "get_script_source_service",
        lambda: pytest.fail("publication reached source lookup"),
    )
    response = client.post(
        "/api/strategies/script-sources/publish",
        headers=_authenticate_human(monkeypatch),
        json={"sourceId": 1, "pricingType": "paid", "price": 5},
    )
    assert response.status_code == 400
    assert response.get_json()["msg"] == "community_publication_must_be_free_and_visible"


def test_admin_review_route_forces_free_only_queue(client, monkeypatch):
    from app.routes import community as community_routes

    captured = {}

    class CommunityService:
        def get_pending_indicators(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}

    monkeypatch.setattr(community_routes, "get_community_service", lambda: CommunityService())
    response = client.get(
        "/api/community/admin/pending-indicators?pricing_type=paid&review_status=pending",
        headers=_authenticate_human(monkeypatch, role="admin"),
    )

    assert response.status_code == 200
    assert "pricing_type" not in captured
