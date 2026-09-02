"""JWT-scoped Smart Insights HTTP API."""

from __future__ import annotations

from flask import g, jsonify, request

from app.observability.features import observe_feature_operation
from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.services.ai_assistant_insights import get_ai_assistant_insights_service
from app.services.smart_insights import get_smart_insights_service
from app.services.smart_insights.response_compaction import (
    compact_pulse_response,
)
from app.utils.auth import admin_required, login_required
from app.utils.logger import get_logger


logger = get_logger(__name__)
smart_insights_blp = Blueprint("smart_insights", __name__)


def _ok(data=None, *, status: int = 200):
    return jsonify({"code": 1, "msg": "success", "data": data}), status


def _fail(msg: str, status: int):
    return jsonify({"code": 0, "msg": msg, "data": None}), status


def _user_id() -> int:
    return int(getattr(g, "user_id", 0) or 0)


def _compact_requested() -> bool:
    return str(request.args.get("compact") or "").strip().lower() in {"1", "true", "yes"}


def _locale() -> str:
    return str(request.args.get("lang") or request.headers.get("Accept-Language") or "vi-VN").split(",", 1)[0]


@smart_insights_blp.route("/overview", methods=["GET"])
@observe_feature_operation("smart_insights", "overview")
@login_required
def overview():
    """Get Smart Insights from the authenticated user's AI Assistant history."""
    try:
        data = get_ai_assistant_insights_service().get_overview(
            user_id=_user_id(),
            as_of=request.args.get("as_of"),
            locale=_locale(),
        )
        return _ok(data)
    except ValueError as exc:
        return _fail(str(exc), 400)
    except Exception:
        logger.exception("smart insights overview failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/dates", methods=["GET"])
@login_required
def dates():
    """List dates with completed AI Assistant analyses for this user/watchlist."""
    try:
        return _ok(
            get_ai_assistant_insights_service().list_dates(user_id=_user_id())
        )
    except ValueError as exc:
        return _fail(str(exc), 400)
    except Exception:
        logger.exception("smart insights dates failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/evidence/<string:evidence_id>", methods=["GET"])
@login_required
def evidence(evidence_id: str):
    """Get one observation with full provenance."""
    try:
        data = get_smart_insights_service().get_evidence(
            user_id=_user_id(), evidence_id=evidence_id
        )
        if data is None:
            return _fail("evidence_not_found", 404)
        return _ok(data)
    except ValueError as exc:
        return _fail(str(exc), 400)
    except Exception:
        logger.exception("smart insights evidence failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/data-health", methods=["GET"])
@observe_feature_operation("smart_insights", "data_health")
@login_required
def data_health():
    """Get source freshness, coverage and latest collector status."""
    try:
        return _ok(get_smart_insights_service().get_data_health(user_id=_user_id()))
    except Exception:
        logger.exception("smart insights data health failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/live-assets", methods=["GET"])
@observe_feature_operation("smart_insights", "live_assets")
@login_required
def live_assets():
    """Return the source-backed assets shown under the application header."""
    try:
        from app.services.smart_insights.live_assets import get_live_asset_snapshot

        return _ok(get_live_asset_snapshot())
    except Exception:
        logger.exception("smart insights live assets failed")
        return _fail("smart_insights_live_assets_unavailable", 503)


@smart_insights_blp.route("/crypto-market-pulse", methods=["GET"])
@observe_feature_operation("smart_insights", "crypto_market_pulse")
@login_required
def crypto_market_pulse():
    """Get all legacy Crypto Pulse tabs from persisted, source-backed evidence."""
    try:
        compact = _compact_requested()
        service_kwargs = {
            "user_id": _user_id(),
            "as_of": request.args.get("as_of"),
            "mode": request.args.get("mode"),
        }
        if compact:
            service_kwargs["compact"] = True
        data = get_smart_insights_service().get_crypto_market_pulse(**service_kwargs)
        if compact:
            data = compact_pulse_response(data)
        return _ok(data)
    except ValueError as exc:
        return _fail(str(exc), 400)
    except Exception:
        logger.exception("smart insights crypto market pulse failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/refresh", methods=["POST"])
@observe_feature_operation("smart_insights", "refresh")
@login_required
@admin_required
def refresh():
    """Queue an audited Smart Insights collector refresh."""
    try:
        payload = request.get_json(silent=True) or {}
        source_codes = payload.get("sourceCodes") or []
        if not isinstance(source_codes, list):
            return _fail("invalid_source_codes", 400)
        data = get_smart_insights_service().queue_refresh(
            requested_by_user_id=_user_id(),
            market=payload.get("market"),
            source_codes=tuple(str(item) for item in source_codes),
        )
        return _ok(data, status=202)
    except ValueError as exc:
        return _fail(str(exc), 400)
    except Exception:
        logger.exception("smart insights refresh queue failed")
        return _fail("smart_insights_refresh_unavailable", 503)


__all__ = ["smart_insights_blp"]
