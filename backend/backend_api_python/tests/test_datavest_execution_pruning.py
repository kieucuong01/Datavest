"""Task 2B1 deletion and retained-boundary regression coverage."""

from __future__ import annotations

import ast
import importlib
import inspect
import re
import subprocess
from pathlib import Path

import pytest

from app.data_sources import crypto as crypto_source
from app.data_sources.factory import DataSourceFactory
from app.services import agent_token_service
from app.utils import agent_auth


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent

TASK_2B1_GROUPS = (
    "broker_credentials",
    "live_orders",
    "trading_worker",
    "live_strategy_deploy",
    "agent_trading_scope",
    "grid_copy_trading",
)

REMOVED_SOURCE_PREFIXES = (
    "backend_api_python/app/services/alpaca_trading/",
    "backend_api_python/app/services/execution_streams/",
    "backend_api_python/app/services/grid/",
    "backend_api_python/app/services/ibkr_trading/",
    "backend_api_python/app/services/live_trading/",
    "backend_api_python/app/services/pending_orders/",
    "backend_api_python/app/services/quick_trade/",
    "backend_api_python/app/services/strategy_runtime/",
)

REMOVED_SOURCE_FILES = {
    "backend_api_python/app/routes/agent_v1/quick_trade.py",
    "backend_api_python/app/routes/agent_v1/runtime.py",
    "backend_api_python/app/routes/agent_v1/trading_data.py",
    "backend_api_python/app/routes/alpaca.py",
    "backend_api_python/app/routes/credentials.py",
    "backend_api_python/app/routes/ibkr.py",
    "backend_api_python/app/routes/quick_trade.py",
    "backend_api_python/app/routes/strategy_account_routes.py",
    "backend_api_python/app/routes/strategy_deviation_routes.py",
    "backend_api_python/app/routes/strategy_executor_routes.py",
    "backend_api_python/app/routes/strategy_grid_routes.py",
    "backend_api_python/app/routes/strategy_ledger_routes.py",
    "backend_api_python/app/routes/strategy_logs_routes.py",
    "backend_api_python/app/routes/strategy_position_ownership_routes.py",
    "backend_api_python/app/routes/strategy_positions_routes.py",
    "backend_api_python/app/services/broker_market_policy.py",
    "backend_api_python/app/services/exchange_execution.py",
    "backend_api_python/app/services/pending_order_position_sync.py",
    "backend_api_python/app/services/pending_order_worker.py",
    "backend_api_python/app/services/strategy_command_client.py",
    "backend_api_python/app/services/strategy_command_repository.py",
    "backend_api_python/app/services/strategy_lifecycle.py",
    "backend_api_python/app/services/strategy_live_guard.py",
    "backend_api_python/app/services/strategy_v2/deployment.py",
    "backend_api_python/app/services/strategy_v2/live_execution.py",
    "backend_api_python/app/services/trading_executor.py",
    "backend_api_python/app/utils/broker_session.py",
    "backend_api_python/app/utils/credential_crypto.py",
    "backend_api_python/app/utils/local_brokers.py",
    "backend_api_python/app/workers/trading.py",
}

REMOVED_MIGRATIONS = {
    "backend_api_python/migrations/20260713_process_roles_and_strategy_commands.sql",
    "backend_api_python/migrations/20260722_alpaca_broker_activities.sql",
    "backend_api_python/migrations/20260722_strategy_funding_fees.sql",
    "backend_api_python/migrations/20260724_execution_stream_ledger.sql",
    "backend_api_python/migrations/20260801_position_ownership.sql",
}

REMOVED_IMPORT_PREFIXES = (
    "app.routes.agent_v1.quick_trade",
    "app.routes.agent_v1.runtime",
    "app.routes.agent_v1.trading_data",
    "app.routes.alpaca",
    "app.routes.credentials",
    "app.routes.ibkr",
    "app.routes.quick_trade",
    "app.routes.strategy_account_routes",
    "app.routes.strategy_deviation_routes",
    "app.routes.strategy_executor_routes",
    "app.routes.strategy_grid_routes",
    "app.routes.strategy_ledger_routes",
    "app.routes.strategy_logs_routes",
    "app.routes.strategy_position_ownership_routes",
    "app.routes.strategy_positions_routes",
    "app.services.alpaca_trading",
    "app.services.broker_market_policy",
    "app.services.exchange_execution",
    "app.services.execution_streams",
    "app.services.grid",
    "app.services.ibkr_trading",
    "app.services.live_trading",
    "app.services.pending_order_position_sync",
    "app.services.pending_order_worker",
    "app.services.pending_orders",
    "app.services.quick_trade",
    "app.services.strategy_command_client",
    "app.services.strategy_command_repository",
    "app.services.strategy_lifecycle",
    "app.services.strategy_live_guard",
    "app.services.strategy_runtime",
    "app.services.strategy_v2.deployment",
    "app.services.strategy_v2.live_execution",
    "app.services.trading_executor",
    "app.utils.broker_session",
    "app.utils.credential_crypto",
    "app.utils.local_brokers",
    "app.workers.trading",
)

PRESERVED_IMPORTS = (
    "app.data_sources.crypto",
    "app.data_sources.factory",
    "app.routes.agent_v1.backtests",
    "app.routes.agent_v1.indicators",
    "app.routes.agent_v1.markets",
    "app.routes.agent_v1.portfolio",
    "app.routes.agent_v1.research",
    "app.routes.agent_v1.strategy_sources",
    "app.routes.backtest_center",
    "app.routes.community",
    "app.routes.factors",
    "app.routes.indicator",
    "app.routes.indicator_signal_alerts",
    "app.routes.kline",
    "app.routes.market",
    "app.routes.portfolio",
    "app.routes.script_source_routes",
    "app.routes.strategy_review_routes",
    "app.services.strategy_authoring",
    "app.services.strategy_review",
    "app.services.strategy_v2.factor_research",
    "app.services.strategy_v2.market_data",
    "app.services.strategy_v2.service",
)

FORBIDDEN_SCHEMA_IDENTIFIERS = {
    "credential_id",
    "exchange_order_id",
    "grid_order_id",
    "pending_order_id",
    "pending_orders",
    "qd_account_positions",
    "qd_exchange_credentials",
    "qd_execution_events",
    "qd_execution_stream_health",
    "qd_live_order_bindings",
    "qd_position_reservations",
    "qd_strategy_broker_activities",
    "qd_strategy_commands",
    "qd_strategy_funding_fees",
    "qd_strategy_runtime_leases",
    "strategy_runtime_events",
    "strategy_runtime_locks",
    "strategy_runtime_state",
}


def _tracked_existing_files() -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return sorted(
        path
        for path in completed.stdout.decode("utf-8").split("\0")
        if path and (REPOSITORY_ROOT / path).is_file()
    )


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_execution_only_sources_and_migrations_are_physically_absent():
    tracked = set(_tracked_existing_files())
    forbidden = sorted(
        path
        for path in tracked
        if path in REMOVED_SOURCE_FILES
        or path in REMOVED_MIGRATIONS
        or path.startswith(REMOVED_SOURCE_PREFIXES)
    )
    assert forbidden == []


def test_production_python_has_no_imports_to_deleted_execution_modules():
    violations: dict[str, list[str]] = {}
    for relative_path in _tracked_existing_files():
        if not relative_path.startswith("backend_api_python/app/") or not relative_path.endswith(".py"):
            continue
        modules = _imported_modules(REPOSITORY_ROOT / relative_path)
        forbidden = sorted(
            module
            for module in modules
            if any(module == prefix or module.startswith(prefix + ".") for prefix in REMOVED_IMPORT_PREFIXES)
        )
        if forbidden:
            violations[relative_path] = forbidden
    assert violations == {}


def test_crypto_data_source_constructs_an_uncredentialed_public_client(monkeypatch):
    captured: dict[str, object] = {}

    class PublicExchange:
        id = "binance"
        markets = {"BTC/USDT": {"active": True}}

        def __init__(self, config):
            captured.update(config)

        def load_markets(self, reload=False):
            assert reload is False

        def fetch_ticker(self, symbol):
            assert symbol == "BTC/USDT"
            return {"symbol": symbol, "last": 123.0}

    monkeypatch.setattr(crypto_source.ccxt, "binance", PublicExchange)

    source = object.__new__(crypto_source.CryptoDataSource)
    source._allow_public_fallback = True
    source._scoped_market_type = "spot"
    source._preferred_public_exchange_id = ""
    source._init_ccxt_exchange("binance", {})

    assert source.get_ticker("BTCUSDT")["last"] == 123.0
    assert {key.lower() for key in captured}.isdisjoint(
        {"apikey", "api_key", "secret", "password", "passphrase", "privatekey"}
    )


def test_crypto_and_factory_expose_only_public_market_data(monkeypatch):
    assert not hasattr(crypto_source, "resolve_ccxt_for_live_trading")
    assert not hasattr(crypto_source.CryptoDataSource, "for_exchange")
    assert not hasattr(crypto_source, "_SCOPED_INSTANCES")
    assert "APIKeys" not in vars(crypto_source)
    factory_source = (BACKEND_ROOT / "app" / "data_sources" / "factory.py").read_text(encoding="utf-8")
    assert '"ibkr"' not in factory_source.lower()
    assert '"alpaca"' not in factory_source.lower()

    forbidden_exchange_calls = {
        "cancel_all_orders",
        "cancel_order",
        "create_limit_order",
        "create_market_order",
        "create_order",
        "fetch_accounts",
        "fetch_balance",
        "fetch_closed_orders",
        "fetch_open_orders",
        "fetch_order",
        "fetch_orders",
        "fetch_positions",
        "set_leverage",
    }
    tree = ast.parse(inspect.getsource(crypto_source))
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called_attributes.isdisjoint(forbidden_exchange_calls)

    selected: dict[str, str] = {}

    def public_market(market_type="spot", preferred_exchange_id=""):
        selected.update(
            market_type=market_type,
            preferred_exchange_id=preferred_exchange_id,
        )
        return object()

    monkeypatch.setattr(crypto_source.CryptoDataSource, "for_public_market", public_market)
    monkeypatch.setattr(
        crypto_source.CryptoDataSource,
        "for_exchange",
        lambda *_args, **_kwargs: pytest.fail("factory selected a live execution venue"),
        raising=False,
    )

    resolved = DataSourceFactory._resolve_source(
        "Crypto",
        exchange_id="okx",
        market_type="swap",
    )

    assert resolved is not None
    assert selected == {"market_type": "swap", "preferred_exchange_id": "okx"}


def test_agent_token_contract_has_only_research_write_backtest_notification_scopes():
    assert agent_auth.ALL_SCOPES == ("R", "W", "B", "N")
    assert all(not hasattr(agent_auth, name) for name in ("SCOPE_T", "SCOPE_C"))
    assert "allow_c_scope" not in inspect.signature(agent_token_service._parse_issue_body).parameters
    assert "allow_c_scope" not in inspect.signature(agent_token_service.issue_agent_token).parameters
    assert agent_token_service.get_token_policy(for_admin=False)["allowed_scopes"] == ["B", "N", "R", "W"]
    assert agent_token_service.get_token_policy(for_admin=True)["allowed_scopes"] == ["B", "N", "R", "W"]


def test_agent_docs_do_not_claim_removed_scopes_or_live_tokens_exist():
    paths = [
        REPOSITORY_ROOT / "README.md",
        REPOSITORY_ROOT / "docs" / "agent" / "AGENT_QUICKSTART.md",
        REPOSITORY_ROOT / "docs" / "agent" / "AI_INTEGRATION_DESIGN.md",
        REPOSITORY_ROOT / "mcp_server" / "README.md",
    ]
    forbidden = re.compile(
        r"(?:\b[TC][ -]?scope\b|\bT/C\b|live-capable token|credentials scope|trading scope)",
        re.IGNORECASE,
    )
    violations = {
        path.relative_to(REPOSITORY_ROOT).as_posix(): sorted(set(forbidden.findall(path.read_text(encoding="utf-8"))))
        for path in paths
        if path.is_file() and forbidden.search(path.read_text(encoding="utf-8"))
    }
    assert violations == {}


def test_execution_only_config_and_public_docs_are_physically_pruned():
    forbidden_by_path = {
        REPOSITORY_ROOT / "backend_api_python" / "env.example": (
            "CREDENTIAL_ENCRYPTION_KEY",
            "IBKR_ORDER_CLIENT_ID",
            "ALPACA_API_KEY",
        ),
        REPOSITORY_ROOT / "backend_api_python" / "docker-entrypoint.sh": (
            "CREDENTIAL_ENCRYPTION_KEY",
            "broker credentials",
        ),
        REPOSITORY_ROOT / "backend_api_python" / "app" / "commands" / "worker_health.py": (
            'choices=("trading",',
            "CREDENTIAL_ENCRYPTION_KEY",
        ),
        REPOSITORY_ROOT / "backend_api_python" / "app" / "openapi" / "tags.py": (
            'POLICY = "Policy"',
            'ACCOUNT = "Account"',
            'CREDENTIALS = "Credentials"',
            'QUICK_TRADE = "QuickTrade"',
            'IBKR = "IBKR"',
            'ALPACA = "Alpaca"',
        ),
        REPOSITORY_ROOT / "backend_api_python" / "app" / "openapi" / "schemas" / "high_risk.py": (
            "CredentialCreateRequestSchema",
            "QuickTradeOrderRequestSchema",
            "StrategyStatusResponseSchema",
        ),
        REPOSITORY_ROOT / "backend_api_python" / "app" / "openapi" / "register.py": (
            '"Credentials"',
            '"QuickTrade"',
            '"Policy"',
        ),
        REPOSITORY_ROOT / "docker-compose.yml": (
            "ALLOW_LOCAL_DESKTOP_BROKERS",
            "SPOT_CLOSE_SAFETY_RATIO",
        ),
        REPOSITORY_ROOT / "docker-compose.ghcr.yml": (
            "ALLOW_LOCAL_DESKTOP_BROKERS",
        ),
        REPOSITORY_ROOT / "README.md": (
            "live execution",
            "CREDENTIAL_ENCRYPTION_KEY",
            "Traditional brokers",
        ),
        REPOSITORY_ROOT / "docs" / "README_CN.md": (
            "实盘执行",
            "CREDENTIAL_ENCRYPTION_KEY",
            "live_trading/",
        ),
    }
    violations = {
        path.relative_to(REPOSITORY_ROOT).as_posix(): [
            token for token in tokens if token.lower() in path.read_text(encoding="utf-8").lower()
        ]
        for path, tokens in forbidden_by_path.items()
        if path.is_file()
        and any(token.lower() in path.read_text(encoding="utf-8").lower() for token in tokens)
    }
    assert violations == {}


def test_mixed_strategy_v2_runtime_exposes_backtest_only():
    runtime_path = BACKEND_ROOT / "app" / "services" / "strategy_v2" / "runtime.py"
    package_path = BACKEND_ROOT / "app" / "services" / "strategy_v2" / "__init__.py"

    runtime_source = runtime_path.read_text(encoding="utf-8")
    package_source = package_path.read_text(encoding="utf-8")

    assert "class StrategyV2BacktestRunner" in runtime_source
    assert "StrategyV2LiveSession" not in runtime_source
    assert "StrategyV2LiveSession" not in package_source


@pytest.mark.parametrize("module_name", PRESERVED_IMPORTS)
def test_research_backtest_indicator_paper_and_mcp_boundaries_remain_importable(module_name):
    assert importlib.import_module(module_name) is not None


def test_fresh_schema_has_no_execution_owned_identifiers():
    violations: dict[str, list[str]] = {}
    for relative_path in _tracked_existing_files():
        if not relative_path.startswith("backend_api_python/migrations/") or not relative_path.endswith(".sql"):
            continue
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8").lower()
        hits = sorted(identifier for identifier in FORBIDDEN_SCHEMA_IDENTIFIERS if identifier in source)
        if hits:
            violations[relative_path] = hits
    assert violations == {}


def test_broker_only_dependencies_are_removed_from_backend_requirements():
    requirements = "\n".join(
        (BACKEND_ROOT / name).read_text(encoding="utf-8")
        for name in ("requirements.txt", "requirements-windows.txt")
    ).lower()
    assert "ib_insync" not in requirements
    assert "alpaca-py" not in requirements
