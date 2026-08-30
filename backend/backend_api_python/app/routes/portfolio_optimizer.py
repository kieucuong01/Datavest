"""JWT-scoped Portfolio Optimizer and paper rebalance API."""

from __future__ import annotations

from flask import g, jsonify, request

from app.observability.features import observe_feature_operation
from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.services.portfolio_optimizer import get_portfolio_optimizer_service
from app.utils.auth import login_required
from app.utils.logger import get_logger


logger = get_logger(__name__)
portfolio_optimizer_blp = Blueprint("portfolio_optimizer", __name__)


def _ok(data=None, *, status=200):
    return jsonify({"code": 1, "msg": "success", "data": data}), status


def _fail(message: str, status: int):
    return jsonify({"code": 0, "msg": message, "data": None}), status


def _user_id() -> int:
    return int(getattr(g, "user_id", 0) or 0)


def _value_error(exc: ValueError):
    message = str(exc)
    if "unavailable" in message:
        return _fail(message, 422)
    if message in {"rebalance_plan_already_applied", "idempotency_key_conflict"}:
        return _fail(message, 409)
    return _fail(message, 400)


@portfolio_optimizer_blp.route("/optimizer/runs", methods=["POST"])
@observe_feature_operation("portfolio_optimizer", "create")
@login_required
def create_optimizer_run():
    """Pin LIVE inputs and run one immutable portfolio optimization."""
    try:
        payload = request.get_json(silent=True) or {}
        return _ok(
            get_portfolio_optimizer_service().create_run(user_id=_user_id(), payload=payload),
            status=201,
        )
    except ValueError as exc:
        return _value_error(exc)
    except Exception:
        logger.exception("portfolio optimizer run failed")
        return _fail("portfolio_optimizer_unavailable", 503)


@portfolio_optimizer_blp.route("/optimizer/runs/<string:run_id>", methods=["GET"])
@login_required
def get_optimizer_run(run_id: str):
    """Get an optimizer run owned by the current user."""
    try:
        result = get_portfolio_optimizer_service().get_run(user_id=_user_id(), run_id=run_id)
        return _ok(result) if result is not None else _fail("optimizer_run_not_found", 404)
    except ValueError as exc:
        return _value_error(exc)
    except Exception:
        logger.exception("portfolio optimizer read failed")
        return _fail("portfolio_optimizer_unavailable", 503)


@portfolio_optimizer_blp.route("/optimizer/runs/<string:run_id>/preview", methods=["POST"])
@login_required
def preview_optimizer_run(run_id: str):
    """Create a paper rebalance proposal without changing the ledger."""
    try:
        payload = request.get_json(silent=True) or {}
        return _ok(
            get_portfolio_optimizer_service().preview(
                user_id=_user_id(),
                run_id=run_id,
                portfolio_value=payload.get("portfolioValue"),
            ),
            status=201,
        )
    except LookupError as exc:
        return _fail(str(exc), 404)
    except (TypeError, ValueError) as exc:
        return _value_error(ValueError(str(exc)))
    except Exception:
        logger.exception("portfolio rebalance preview failed")
        return _fail("portfolio_optimizer_unavailable", 503)


@portfolio_optimizer_blp.route("/optimizer/runs/<string:run_id>/apply", methods=["POST"])
@observe_feature_operation("portfolio_optimizer", "paper_apply")
@login_required
def apply_optimizer_run(run_id: str):
    """Apply a confirmed proposal to the paper portfolio only."""
    try:
        payload = request.get_json(silent=True) or {}
        return _ok(
            get_portfolio_optimizer_service().apply(
                user_id=_user_id(),
                run_id=run_id,
                plan_id=str(payload.get("planId") or ""),
                idempotency_key=str(payload.get("idempotencyKey") or ""),
            )
        )
    except LookupError as exc:
        return _fail(str(exc), 404)
    except ValueError as exc:
        return _value_error(exc)
    except RuntimeError as exc:
        return _fail(str(exc), 409)
    except Exception:
        logger.exception("portfolio rebalance apply failed")
        return _fail("portfolio_optimizer_unavailable", 503)


__all__ = ["portfolio_optimizer_blp"]
