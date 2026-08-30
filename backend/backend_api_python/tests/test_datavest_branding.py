"""DataVest derivative branding contracts."""

from app.services.settings.branding import BRAND_DEFAULTS, build_brand_config


def test_datavest_brand_defaults_preserve_quantdinger_attribution(monkeypatch):
    for key in (
        "BRAND_APP_NAME",
        "BRAND_COPYRIGHT",
        "BRAND_CONTACT_EMAIL",
        "BRAND_CONTACT_SUPPORT_URL",
        "BRAND_CONTACT_LIVE_CHAT_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    config = build_brand_config("test")

    assert BRAND_DEFAULTS["app_name"] == "DataVest"
    assert config["app_name"] == "DataVest"
    assert "Powered by QuantDinger" in config["copyright"]
    assert config["contact"]["email"] == ""
    assert config["contact"]["support_url"] == ""
