"""JWT-scoped Smart Insights HTTP API."""

from __future__ import annotations

from flask import Response, g, jsonify, request

from app.observability.features import observe_feature_operation
from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.services.ai_assistant_insights import get_ai_assistant_insights_service
from app.services.smart_insights import get_smart_insights_service
from app.services.smart_insights.public_access import get_public_smart_insights_service
from app.services.smart_insights.public_reports import (
    PUBLIC_RESEARCH_ASSET_SCOPE,
    PUBLIC_RESEARCH_LOCALE,
    public_asset_key,
)
from app.services.smart_insights.shared_research_access import SharedResearchAccessService
from app.services.ai_report_pdf import (
    build_trading_agents_report_pdf,
    build_trading_agents_summary_pdf,
)
from app.services.smart_insights.response_compaction import (
    compact_overview_response,
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


def _shared_research() -> SharedResearchAccessService:
    return SharedResearchAccessService()


@smart_insights_blp.route("/public/overview", methods=["GET"])
@observe_feature_operation("smart_insights", "overview")
def public_overview():
    """Return the fixed BTC/VNINDEX/XAU shared research view."""
    try:
        data = get_public_smart_insights_service().get_overview(
            as_of=request.args.get("as_of"), locale=_locale()
        )
        if _compact_requested():
            data = compact_overview_response(data)
        return _ok(data)
    except ValueError as exc:
        return _fail(str(exc), 400)
    except Exception:
        logger.exception("public smart insights overview failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/public/dates", methods=["GET"])
def public_dates():
    try:
        return _ok(get_public_smart_insights_service().list_dates())
    except Exception:
        logger.exception("public smart insights dates failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/public/evidence/<string:evidence_id>", methods=["GET"])
def public_evidence(evidence_id: str):
    try:
        data = get_public_smart_insights_service().get_evidence(evidence_id)
        return _ok(data) if data is not None else _fail("evidence_not_found", 404)
    except ValueError as exc:
        return _fail(str(exc), 400)
    except Exception:
        logger.exception("public smart insights evidence failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/public/data-health", methods=["GET"])
@observe_feature_operation("smart_insights", "data_health")
def public_data_health():
    try:
        return _ok(get_public_smart_insights_service().get_data_health())
    except Exception:
        logger.exception("public smart insights data health failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/public/live-assets", methods=["GET"])
@observe_feature_operation("smart_insights", "live_assets")
def public_live_assets():
    try:
        return _ok(get_public_smart_insights_service().get_live_assets())
    except Exception:
        logger.exception("public smart insights live assets failed")
        return _fail("smart_insights_live_assets_unavailable", 503)


@smart_insights_blp.route(
    "/public/reports/<path:asset_key>/deep.pdf", methods=["GET"]
)
def public_deep_report_pdf(asset_key: str):
    """Render a safe, tenant-free deep report for the guest PDF reader."""
    try:
        data = get_public_smart_insights_service().get_public_report(
            asset_key=asset_key, report_kind="deep", locale=_locale()
        )
        body = str((data or {}).get("body") or "").strip()
        asset = next(
            (
                item
                for item in PUBLIC_RESEARCH_ASSET_SCOPE
                if public_asset_key(item) == str(asset_key or "").strip()
            ),
            None,
        )
        if not body or asset is None:
            return _fail("public_report_not_found", 404)
        analysis_date = str((data or {}).get("effectiveDate") or "")
        pdf_bytes = build_trading_agents_report_pdf(
            content=body,
            market=str(asset["market"]),
            symbol=str(asset["symbol"]),
            analysis_date=analysis_date,
            language=PUBLIC_RESEARCH_LOCALE,
            # Do not expose the private TradingAgents run identifier. The
            # public PDF is rendered from the already-published payload.
            run_id="public-report",
        )
    except ValueError:
        return _fail("public_report_not_found", 404)
    except ImportError:
        return _fail("smart_insights_pdf_dependency_missing", 500)
    except Exception:
        logger.exception("public smart insights deep report PDF failed")
        return _fail("smart_insights_pdf_unavailable", 503)

    symbol = str(asset["displaySymbol"]).strip() or "report"
    date_text = str((data or {}).get("effectiveDate") or "").replace("-", "") or "latest"
    filename = f"DataVest_TradingAgents_{symbol}_{date_text}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "Cache-Control": "no-store, max-age=0",
        },
    )


@smart_insights_blp.route(
    "/public/reports/<path:asset_key>/deep-summary.pdf", methods=["GET"]
)
def public_deep_summary_pdf(asset_key: str):
    """Render the safe guest digest from the published deep-report payload."""
    try:
        data = get_public_smart_insights_service().get_public_report(
            asset_key=asset_key, report_kind="deep", locale=_locale()
        )
        body = str((data or {}).get("body") or "").strip()
        asset = next(
            (
                item
                for item in PUBLIC_RESEARCH_ASSET_SCOPE
                if public_asset_key(item) == str(asset_key or "").strip()
            ),
            None,
        )
        if not body or asset is None:
            return _fail("public_report_not_found", 404)
        analysis_date = str((data or {}).get("effectiveDate") or "")
        pdf_bytes = build_trading_agents_summary_pdf(
            content=body,
            market=str(asset["market"]),
            symbol=str(asset["symbol"]),
            analysis_date=analysis_date,
            language=PUBLIC_RESEARCH_LOCALE,
            # Public reports never reveal account-owned TradingAgents runs.
            run_id="public-report",
        )
    except ValueError:
        return _fail("public_report_not_found", 404)
    except ImportError:
        return _fail("smart_insights_pdf_dependency_missing", 500)
    except Exception:
        logger.exception("public smart insights deep summary PDF failed")
        return _fail("smart_insights_pdf_unavailable", 503)

    symbol = str(asset["displaySymbol"]).strip() or "report"
    date_text = str((data or {}).get("effectiveDate") or "").replace("-", "") or "latest"
    filename = f"DataVest_TradingAgents_Summary_{symbol}_{date_text}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "Cache-Control": "no-store, max-age=0",
        },
    )


@smart_insights_blp.route(
    "/public/reports/<path:asset_key>/<string:report_kind>", methods=["GET"]
)
def public_report(asset_key: str, report_kind: str):
    """Read a final public report without entering an account-owned boundary."""
    try:
        data = get_public_smart_insights_service().get_public_report(
            asset_key=asset_key, report_kind=report_kind, locale=_locale()
        )
        return _ok(data) if data is not None else _fail("public_report_not_found", 404)
    except ValueError:
        return _fail("public_report_not_found", 404)
    except Exception:
        logger.exception("public smart insights report failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/research/reports", methods=["GET"])
@login_required
def shared_research_reports():
    """List safe reusable report states for common assets and this user's watchlist."""
    try:
        return _ok(_shared_research().list_states(user_id=_user_id()))
    except Exception:
        logger.exception("shared smart insights reports list failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/research/reports/<path:asset_key>/deep.pdf", methods=["GET"])
@login_required
def shared_deep_report_pdf(asset_key: str):
    """Render a viewer-safe PDF after checking current watchlist membership."""
    try:
        service = _shared_research()
        _scope, asset = service.resolve_asset(_user_id(), asset_key)
        state = service.state(user_id=_user_id(), asset_key=asset_key, report_kind="deep")
        report = state.get("report") or {}
        body = str(report.get("body") or "").strip()
        if not body:
            return _fail("shared_report_not_found", 404)
        pdf_bytes = build_trading_agents_report_pdf(
            content=body, market=str(asset["market"]), symbol=str(asset["symbol"]),
            analysis_date=str(report.get("effectiveDate") or ""), language=PUBLIC_RESEARCH_LOCALE,
            run_id="shared-report",
        )
    except ValueError:
        return _fail("shared_report_not_found", 404)
    except ImportError:
        return _fail("smart_insights_pdf_dependency_missing", 500)
    except Exception:
        logger.exception("shared smart insights deep report PDF failed")
        return _fail("smart_insights_pdf_unavailable", 503)
    filename = f"DataVest_TradingAgents_{str(asset.get('displaySymbol') or 'report')}_{str(report.get('effectiveDate') or 'latest').replace('-', '')}.pdf"
    return Response(pdf_bytes, mimetype="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(len(pdf_bytes)), "Cache-Control": "no-store, max-age=0",
    })


@smart_insights_blp.route("/research/reports/<path:asset_key>/deep-summary.pdf", methods=["GET"])
@login_required
def shared_deep_summary_pdf(asset_key: str):
    try:
        service = _shared_research()
        _scope, asset = service.resolve_asset(_user_id(), asset_key)
        state = service.state(user_id=_user_id(), asset_key=asset_key, report_kind="deep")
        report = state.get("report") or {}
        body = str(report.get("body") or "").strip()
        if not body:
            return _fail("shared_report_not_found", 404)
        pdf_bytes = build_trading_agents_summary_pdf(
            content=body, market=str(asset["market"]), symbol=str(asset["symbol"]),
            analysis_date=str(report.get("effectiveDate") or ""), language=PUBLIC_RESEARCH_LOCALE,
            run_id="shared-report",
        )
    except ValueError:
        return _fail("shared_report_not_found", 404)
    except ImportError:
        return _fail("smart_insights_pdf_dependency_missing", 500)
    except Exception:
        logger.exception("shared smart insights deep summary PDF failed")
        return _fail("smart_insights_pdf_unavailable", 503)
    filename = f"DataVest_TradingAgents_Summary_{str(asset.get('displaySymbol') or 'report')}_{str(report.get('effectiveDate') or 'latest').replace('-', '')}.pdf"
    return Response(pdf_bytes, mimetype="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(len(pdf_bytes)), "Cache-Control": "no-store, max-age=0",
    })


@smart_insights_blp.route("/research/reports/<path:asset_key>/<string:report_kind>", methods=["GET"])
@login_required
def shared_research_report(asset_key: str, report_kind: str):
    try:
        return _ok(_shared_research().state(
            user_id=_user_id(), asset_key=asset_key, report_kind=report_kind,
        ))
    except ValueError:
        return _fail("shared_report_not_found", 404)
    except Exception:
        logger.exception("shared smart insights report read failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/research/reports/<path:asset_key>/<string:report_kind>", methods=["POST"])
@login_required
def request_shared_research_report(asset_key: str, report_kind: str):
    """Claim the current period once, then queue reusable analysis off-request."""
    try:
        result = _shared_research().request(
            user_id=_user_id(), asset_key=asset_key, report_kind=report_kind,
        )
        return _ok(result, status=202 if result.get("claimed") else 200)
    except ValueError:
        return _fail("shared_report_not_found", 404)
    except Exception:
        logger.exception("shared smart insights report request failed")
        return _fail("smart_insights_unavailable", 503)


@smart_insights_blp.route("/public/crypto-market-pulse", methods=["GET"])
@observe_feature_operation("smart_insights", "crypto_market_pulse")
def public_crypto_market_pulse():
    try:
        service_kwargs = {
            "as_of": request.args.get("as_of"),
            "compact": _compact_requested(),
        }
        stage = request.args.get("stage")
        if stage:
            service_kwargs["stage"] = stage
        data = get_public_smart_insights_service().get_crypto_market_pulse(**service_kwargs)
        if _compact_requested():
            data = compact_pulse_response(data)
        return _ok(data)
    except ValueError as exc:
        return _fail(str(exc), 400)
    except Exception:
        logger.exception("public smart insights crypto market pulse failed")
        return _fail("smart_insights_unavailable", 503)


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
        if _compact_requested():
            data = compact_overview_response(data)
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
        stage = request.args.get("stage")
        if stage:
            service_kwargs["stage"] = stage
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
