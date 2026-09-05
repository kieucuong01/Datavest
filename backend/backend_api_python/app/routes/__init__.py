"""
API Routes Module — Agent Gateway + OpenAPI-registered human routes.
"""
from flask import Flask


def register_routes(app: Flask):
    """Register Agent Gateway and human web API (via flask-smorest)."""
    from app.openapi import init_openapi
    init_openapi(app)

    # This route is HMAC-protected and receives traffic only from the private
    # TradingAgents Compose network. It is intentionally separate from the
    # user-facing TradingAgents API added in the next integration task.
    from app.services.trading_agents import create_internal_callback_blueprint
    app.register_blueprint(create_internal_callback_blueprint())

    from app.routes.agent_v1 import register as register_agent_v1
    register_agent_v1(app)
