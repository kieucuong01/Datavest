"""Release gates for the free, source-visible DataVest library."""

from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent


def test_payment_and_paid_library_modules_are_physically_absent():
    removed_modules = (
        "app.routes.billing",
        "app.services.billing_config",
        "app.services.billing_service",
        "app.services.usdt_payment_service",
        "app.services.usdt_payment",
        "app.services.community_service",
        "app.services.strategy_assets",
    )
    for module_name in removed_modules:
        assert importlib.util.find_spec(module_name) is None, module_name


def test_fresh_schema_has_no_account_balance_payment_or_paid_source_objects():
    sql = (BACKEND_ROOT / "migrations" / "init.sql").read_text(encoding="utf-8").lower()
    forbidden = (
        "qd_credits_log",
        "qd_membership_orders",
        "qd_usdt_orders",
        "qd_indicator_purchases",
        "vip_expires_at",
        "vip_plan",
        "vip_is_lifetime",
        "pricing_type",
        "vip_free",
        "is_encrypted",
        "purchase_count",
        "source_marketplace_indicator_id",
    )
    for token in forbidden:
        assert token not in sql, token
    for retained in (
        "qd_users",
        "qd_indicator_codes",
        "qd_indicator_code_versions",
        "qd_indicator_comments",
        "qd_script_sources",
        "qd_script_source_versions",
        "qd_backtest_runs",
        "qd_manual_positions",
        "qd_agent_paper_orders",
    ):
        assert f"create table if not exists {retained}" in sql, retained


def test_removed_http_surfaces_are_true_404(client):
    requests = (
        ("GET", "/api/billing/config"),
        ("POST", "/api/billing/usdt/create-order"),
        ("POST", "/api/community/indicators/1/purchase"),
        ("POST", "/api/community/indicators/1/sync"),
        ("GET", "/api/community/my-purchases"),
        ("GET", "/api/users/credits-log"),
        ("GET", "/api/users/admin-orders"),
    )
    for method, path in requests:
        response = client.open(path, method=method, json={})
        assert response.status_code == 404, (method, path, response.status_code)


def test_free_library_routes_remain_registered(app):
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/community/indicators" in paths
    assert "/api/community/indicators/<int:indicator_id>" in paths
    assert "/api/community/indicators/<int:indicator_id>/fork" in paths
    assert "/api/community/indicators/<int:indicator_id>/comments" in paths
    assert "/api/community/author/indicators/<int:indicator_id>/unpublish" in paths
    assert "/api/strategies/script-sources/publish" in paths


def test_environment_template_keeps_deepseek_server_side_without_product_payment_keys():
    env = (BACKEND_ROOT / "env.example").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=" in env
    for key in (
        "BILLING_ENABLED",
        "CREDITS_REGISTER_BONUS",
        "MEMBERSHIP_MONTHLY_PRICE_USD",
        "USDT_PAY_ENABLED",
        "MARKETPLACE_PLATFORM_FEE_RATE",
    ):
        assert key not in env


def test_fork_copies_visible_source_and_records_lineage(monkeypatch):
    from app.services import community_library

    executed = []

    class Cursor:
        lastrowid = 42

        def execute(self, sql, params=None):
            executed.append((sql, params))

        def close(self):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            pass

    @contextmanager
    def fake_db():
        yield Connection()

    library = community_library.CommunityLibrary()
    monkeypatch.setattr(community_library, "get_db_connection", fake_db)
    monkeypatch.setattr(
        library,
        "get_indicator_detail",
        lambda *_args, **_kwargs: {
            "id": 7,
            "name": "EMA Research",
            "description": "Visible source",
            "code": "output = {'plots': [], 'signals': []}",
            "asset_type": "indicator",
            "source_script_source_id": None,
            "source_strategy_id": None,
        },
    )

    ok, message, data = library.fork_free_indicator(buyer_id=9, indicator_id=7)

    assert (ok, message) == (True, "forked")
    assert data == {"local_copy_id": 42, "source_indicator_id": 7}
    insert_sql, insert_params = executed[0]
    assert "source_indicator_id" in insert_sql
    assert "output = {'plots': [], 'signals': []}" in insert_params
    assert 7 in insert_params
