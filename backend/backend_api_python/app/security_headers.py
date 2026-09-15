"""Response security headers with a safe CSP rollout path."""

from __future__ import annotations

from flask import Flask


_CSP_REPORT_ONLY = "; ".join(
    (
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'self'",
        "form-action 'self'",
        "script-src 'self' 'unsafe-inline' https:",
        "style-src 'self' 'unsafe-inline' https:",
        "img-src 'self' data: blob: https:",
        "font-src 'self' data: https:",
        "connect-src 'self' https: wss:",
        "media-src 'self' data: blob: https:",
        "frame-src 'self' blob: https:",
        "worker-src 'self' blob:",
    )
)


def init_security_headers(app: Flask) -> None:
    """Attach a non-blocking CSP so violations can be observed before enforcement."""

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("Content-Security-Policy-Report-Only", _CSP_REPORT_ONLY)
        return response


__all__ = ["init_security_headers"]
