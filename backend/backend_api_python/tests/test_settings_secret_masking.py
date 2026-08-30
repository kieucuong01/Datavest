from types import SimpleNamespace

import pytest


def test_settings_values_masks_password_fields(client, monkeypatch):
    import app.routes.settings as settings_route
    import app.utils.auth as auth_mod

    monkeypatch.setattr(auth_mod, "verify_token", lambda token: {
        "sub": "admin",
        "user_id": 1,
        "role": "admin",
        "_verified_username": "admin",
        "_verified_user_role": "admin",
    })
    monkeypatch.setattr(settings_route, "read_env_file", lambda: {
        "CUSTOM_API_KEY": "real-secret",
        "LLM_PROVIDER": "custom",
    })
    monkeypatch.setattr(settings_route, "CONFIG_SCHEMA", {
        "ai": {
            "items": [
                {"key": "CUSTOM_API_KEY", "type": "password"},
                {"key": "LLM_PROVIDER", "type": "select"},
            ]
        }
    })

    resp = client.get("/api/settings/values", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]["ai"]
    assert data["CUSTOM_API_KEY"] == ""
    assert data["CUSTOM_API_KEY_configured"] is True
    assert data["LLM_PROVIDER"] == "custom"


def test_settings_values_does_not_treat_password_default_as_configured(client, monkeypatch):
    import app.routes.settings as settings_route
    import app.utils.auth as auth_mod

    monkeypatch.setattr(auth_mod, "verify_token", lambda token: {
        "sub": "admin",
        "user_id": 1,
        "role": "admin",
        "_verified_username": "admin",
        "_verified_user_role": "admin",
    })
    monkeypatch.setattr(settings_route, "read_env_file", lambda: {})
    monkeypatch.setattr(settings_route, "CONFIG_SCHEMA", {
        "security": {
            "items": [
                {"key": "ADMIN_PASSWORD", "type": "password", "default": "123456"},
            ]
        }
    })

    resp = client.get("/api/settings/values", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]["security"]
    assert data["ADMIN_PASSWORD"] == ""
    assert data["ADMIN_PASSWORD_configured"] is False


def test_secret_key_save_requires_restart_without_hot_reload(client, monkeypatch):
    import app.routes.settings as settings_route
    import app.utils.auth as auth_mod

    monkeypatch.setattr(auth_mod, "verify_token", lambda token: {
        "sub": "admin",
        "user_id": 1,
        "role": "admin",
        "_verified_username": "admin",
        "_verified_user_role": "admin",
    })
    monkeypatch.setattr(settings_route, "CONFIG_SCHEMA", {
        "auth": {
            "items": [
                {"key": "SECRET_KEY", "type": "password"},
            ]
        }
    })
    monkeypatch.setattr(
        settings_route,
        "read_env_file",
        lambda: {"SECRET_KEY": "current-persisted-secret"},
    )

    written = {}
    runtime_calls = []
    monkeypatch.setattr(
        settings_route,
        "write_env_file",
        lambda values: written.update(values) is None,
    )
    monkeypatch.setattr(
        settings_route,
        "clear_config_cache",
        lambda: runtime_calls.append("clear"),
    )
    monkeypatch.setattr(
        settings_route,
        "reload_runtime_env",
        lambda: runtime_calls.append("reload"),
    )
    monkeypatch.setattr(
        settings_route,
        "refresh_runtime_services",
        lambda: runtime_calls.append("refresh"),
    )

    resp = client.post(
        "/api/settings/save",
        headers={"Authorization": "Bearer token"},
        json={"auth": {"SECRET_KEY": "next-persisted-secret"}},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["code"] == 1
    assert written["SECRET_KEY"] == "next-persisted-secret"
    assert payload["data"]["requires_restart"] is True
    assert payload["data"]["restart_required_keys"] == ["SECRET_KEY"]
    assert payload["data"]["hot_reloaded"] is False
    assert payload["data"]["services_refreshed"] is False
    assert runtime_calls == []


def test_ai_setting_save_hot_reloads_without_restarting(client, monkeypatch):
    import app.routes.settings as settings_route
    import app.utils.auth as auth_mod

    monkeypatch.setattr(auth_mod, "verify_token", lambda token: {
        "sub": "admin",
        "user_id": 1,
        "role": "admin",
        "_verified_username": "admin",
        "_verified_user_role": "admin",
    })
    monkeypatch.setattr(settings_route, "CONFIG_SCHEMA", {
        "ai": {
            "items": [
                {"key": "LLM_PROVIDER", "type": "select"},
            ]
        }
    })
    monkeypatch.setattr(
        settings_route,
        "read_env_file",
        lambda: {"LLM_PROVIDER": "openrouter"},
    )
    monkeypatch.setattr(settings_route, "write_env_file", lambda values: True)

    runtime_calls = []
    monkeypatch.setattr(
        settings_route,
        "clear_config_cache",
        lambda: runtime_calls.append("clear"),
    )
    monkeypatch.setattr(
        settings_route,
        "reload_runtime_env",
        lambda: runtime_calls.append("reload"),
    )
    monkeypatch.setattr(
        settings_route,
        "refresh_runtime_services",
        lambda: runtime_calls.append("refresh"),
    )

    resp = client.post(
        "/api/settings/save",
        headers={"Authorization": "Bearer token"},
        json={"ai": {"LLM_PROVIDER": "deepseek"}},
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["code"] == 1
    assert payload["data"]["requires_restart"] is False
    assert payload["data"]["restart_required_keys"] == []
    assert payload["data"]["hot_reloaded_keys"] == ["LLM_PROVIDER"]
    assert payload["data"]["hot_reloaded"] is True
    assert payload["data"]["services_refreshed"] is True
    assert runtime_calls == ["clear", "reload", "refresh"]
FORBIDDEN_SETTINGS = {
    "ORDER_MODE",
    "MAKER_WAIT_SEC",
    "SPOT_CLOSE_SAFETY_RATIO",
    "SPOT_OPEN_QUOTE_BUFFER",
    "ALLOW_LOCAL_DESKTOP_BROKERS",
    "ENABLE_PENDING_ORDER_WORKER",
    "DISABLE_RESTORE_RUNNING_STRATEGIES",
    "AGENT_LIVE_TRADING_ENABLED",
    "BILLING_ENABLED",
    "MEMBERSHIP_MONTHLY_CREDITS",
    "USDT_PAY_ENABLED",
    "USDT_TRC20_ADDRESS",
    "BILLING_COST_BACKTEST",
    "CREDITS_REGISTER_BONUS",
    "MARKETPLACE_PLATFORM_FEE_RATE",
}


def _admin_headers(monkeypatch):
    import app.utils.auth as auth_mod

    monkeypatch.setattr(auth_mod, "verify_token", lambda _token: {
        "sub": "admin",
        "user_id": 1,
        "role": "admin",
        "_verified_username": "admin",
        "_verified_user_role": "admin",
    })
    return {"Authorization": "Bearer token"}


def _flatten_setting_keys(groups):
    return {
        item["key"]
        for group in groups.values()
        for item in group.get("items", [])
    }


def test_reachable_settings_schema_and_values_exclude_removed_product_controls(client, monkeypatch):
    import app.routes.settings as settings_route

    headers = _admin_headers(monkeypatch)
    monkeypatch.setattr(settings_route, "read_env_file", lambda: {
        "LLM_PROVIDER": "deepseek",
        "CCXT_DEFAULT_EXCHANGE": "binance",
        "ALLOW_LOCAL_DESKTOP_BROKERS": "true",
        "AGENT_LIVE_TRADING_ENABLED": "true",
        "BILLING_ENABLED": "true",
        "USDT_PAY_ENABLED": "true",
    })

    schema_response = client.get("/api/settings/schema", headers=headers)
    values_response = client.get("/api/settings/values", headers=headers)

    assert schema_response.status_code == 200
    schema = schema_response.get_json()["data"]
    assert "trading" not in schema
    assert "billing" not in schema
    assert _flatten_setting_keys(schema).isdisjoint(FORBIDDEN_SETTINGS)

    assert values_response.status_code == 200
    values = values_response.get_json()["data"]
    assert "trading" not in values
    assert "billing" not in values
    assert {key for group in values.values() for key in group}.isdisjoint(FORBIDDEN_SETTINGS)
    assert values["ai"]["LLM_PROVIDER"] == "deepseek"
    assert values["data_source"]["CCXT_DEFAULT_EXCHANGE"] == "binance"


@pytest.mark.parametrize(
    ("group", "key"),
    [
        ("billing", "BILLING_ENABLED"),
        ("billing", "CREDITS_REGISTER_BONUS"),
        ("billing", "USDT_PAY_ENABLED"),
    ],
)
def test_settings_save_rejects_removed_product_keys(client, monkeypatch, group, key):
    import app.routes.settings as settings_route

    headers = _admin_headers(monkeypatch)
    monkeypatch.setattr(settings_route, "read_env_file", lambda: {})
    monkeypatch.setattr(
        settings_route,
        "write_env_file",
        lambda _values: pytest.fail("forbidden setting reached persistence"),
    )

    response = client.post(
        "/api/settings/save",
        headers=headers,
        json={group: {key: "true"}},
    )

    assert response.status_code == 400
    assert response.get_json()["msg"] == "forbidden_setting"
    assert response.get_json()["data"]["keys"] == [key]


def test_safe_provider_settings_still_save_and_hot_reload(client, monkeypatch):
    import app.routes.settings as settings_route

    headers = _admin_headers(monkeypatch)
    written = {}
    runtime_calls = []
    monkeypatch.setattr(settings_route, "read_env_file", lambda: {})
    monkeypatch.setattr(settings_route, "write_env_file", lambda values: written.update(values) is None)
    monkeypatch.setattr(settings_route, "clear_config_cache", lambda: runtime_calls.append("clear"))
    monkeypatch.setattr(settings_route, "reload_runtime_env", lambda: runtime_calls.append("reload"))
    monkeypatch.setattr(settings_route, "refresh_runtime_services", lambda: runtime_calls.append("refresh"))

    response = client.post(
        "/api/settings/save",
        headers=headers,
        json={
            "ai": {"LLM_PROVIDER": "deepseek"},
            "data_source": {"CCXT_DEFAULT_EXCHANGE": "binance"},
        },
    )

    assert response.status_code == 200
    assert response.get_json()["code"] == 1
    assert written["LLM_PROVIDER"] == "deepseek"
    assert written["CCXT_DEFAULT_EXCHANGE"] == "binance"
    assert runtime_calls == ["clear", "reload", "refresh"]


def test_runtime_refresh_does_not_import_billing_or_payment_modules(monkeypatch):
    from app.services.settings import runtime

    imported = []
    monkeypatch.setattr(
        runtime.importlib,
        "import_module",
        lambda name: imported.append(name) or SimpleNamespace(),
    )

    runtime.refresh_runtime_services()

    assert "app.services.billing_service" not in imported
    assert "app.services.usdt_payment_service" not in imported
