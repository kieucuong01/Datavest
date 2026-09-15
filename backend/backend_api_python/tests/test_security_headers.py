"""Security-header contract tests."""

from flask import Flask
from pathlib import Path


def test_csp_starts_in_report_only_mode():
    from app.security_headers import init_security_headers

    app = Flask(__name__)
    init_security_headers(app)

    @app.get("/probe")
    def probe():
        return {"ok": True}

    response = app.test_client().get("/probe")

    policy = response.headers["Content-Security-Policy-Report-Only"]
    assert "default-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'self'" in policy
    assert "Content-Security-Policy" not in response.headers


def test_vps_proxy_uses_csp_report_only_before_enforcement():
    repository_root = Path(__file__).resolve().parents[3]
    config = (repository_root / "deploy" / "vps" / "nginx.conf").read_text(encoding="utf-8")

    assert "Content-Security-Policy-Report-Only" in config
    assert "add_header Content-Security-Policy " not in config
