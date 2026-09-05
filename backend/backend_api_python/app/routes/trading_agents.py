"""JWT-protected research gateway for the private TradingAgents runtime."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import date, datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from flask import Response, g, jsonify, request, stream_with_context

from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.tasks.trading_agents import (
    TradingAgentsServiceUnavailable,
    enqueue_trading_agents_control,
    enqueue_trading_agents_run,
    fetch_artifact_from_service,
)
from app.utils.auth import login_required
from app.utils.logger import get_logger


logger = get_logger(__name__)
trading_agents_blp = Blueprint("trading_agents", __name__)

UPSTREAM_SOURCE_PIN = "TauricResearch/TradingAgents@9dee508c44662702281a8dbaad1f7b42179b5ba7"
FULL_ANALYST_SELECTION = ("market", "social", "news", "fundamentals")
_SUPPORTED_MARKETS = frozenset({"Crypto", "VNStock", "Gold"})
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_SENSITIVE_CONFIG_PARTS = ("api_key", "apikey", "authorization", "cookie", "password", "secret", "token")
_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


def get_repository():
    from app.services.trading_agents_repository import TradingAgentsRepository

    return TradingAgentsRepository()


def enqueue_run(run_id: str):
    return enqueue_trading_agents_run(run_id)


def _ok(data: Any = None, *, status: int = 200):
    return jsonify({"code": 1, "msg": "success", "data": data}), status


def _fail(code: str, status: int):
    return jsonify({"code": 0, "msg": code, "data": None}), status


def _user_id() -> int:
    return int(getattr(g, "user_id", 0) or 0)


def _today_vietnam() -> str:
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()


def _validate_request(payload: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise ValueError("invalid_request")
    market = str(payload.get("market") or "").strip()
    symbol = str(payload.get("symbol") or "").strip()
    if market not in _SUPPORTED_MARKETS or not symbol or len(symbol) > 80:
        raise ValueError("unsupported_market_or_symbol")
    analysis_date = str(payload.get("analysisDate") or payload.get("analysis_date") or _today_vietnam()).strip()
    try:
        date.fromisoformat(analysis_date)
    except ValueError as exc:
        raise ValueError("invalid_analysis_date") from exc
    native_config = payload.get("nativeConfig") or payload.get("native_config") or {}
    if not isinstance(native_config, Mapping) or not _safe_native_config(native_config):
        raise ValueError("invalid_native_config")
    requested_analysts = payload.get("selectedAnalysts") or payload.get("selected_analysts") or FULL_ANALYST_SELECTION
    if tuple(requested_analysts) != FULL_ANALYST_SELECTION:
        raise ValueError("full_upstream_analyst_selection_required")
    request_record = {
        "market": market,
        "symbol": symbol,
        "analysis_date": analysis_date,
        "language": str(payload.get("language") or "vi-VN")[:16],
        "evidence_ref": str(payload.get("evidenceRef") or payload.get("evidence_ref") or "")[:160],
    }
    config_record = {
        "native_config": dict(native_config),
        "selected_analysts": list(FULL_ANALYST_SELECTION),
    }
    return request_record, config_record


def _safe_native_config(value: Mapping[str, Any], *, depth: int = 0) -> bool:
    if depth > 5 or len(value) > 80:
        return False
    for key, item in value.items():
        key_text = str(key).lower().replace("-", "_")
        if any(part in key_text for part in _SENSITIVE_CONFIG_PARTS):
            return False
        if isinstance(item, Mapping) and not _safe_native_config(item, depth=depth + 1):
            return False
        if isinstance(item, list) and (len(item) > 100 or any(isinstance(entry, Mapping) and not _safe_native_config(entry, depth=depth + 1) for entry in item)):
            return False
        if isinstance(item, str) and len(item) > 400:
            return False
    return True


def _public_run(record: Mapping[str, Any]) -> dict[str, Any]:
    request_json = record.get("request_json") or {}
    if isinstance(request_json, str):
        try:
            request_json = json.loads(request_json)
        except (TypeError, ValueError):
            request_json = {}
    return {
        "run_id": record.get("run_id"),
        "status": record.get("status"),
        "market": request_json.get("market"),
        "symbol": request_json.get("symbol"),
        "analysis_date": request_json.get("analysis_date"),
        "source_pin": record.get("source_pin"),
        "created_at": record.get("created_at"),
        "started_at": record.get("started_at"),
        "finished_at": record.get("finished_at"),
        "failure_code": record.get("failure_code"),
        "failure_message": record.get("failure_message"),
        "artifacts": record.get("artifacts") or [],
        "proposal": record.get("proposal"),
    }


@trading_agents_blp.route("/runs", methods=["POST"])
@login_required
def create_run():
    try:
        request_record, config_record = _validate_request(request.get_json(silent=True) or {})
        repository = get_repository()
        run = repository.create_run(
            user_id=_user_id(),
            request=request_record,
            config=config_record,
            source_pin=UPSTREAM_SOURCE_PIN,
            run_id=uuid.uuid4().hex,
        )
        try:
            enqueue_run(str(run["run_id"]))
        except Exception:
            repository.transition_run(
                run_id=str(run["run_id"]),
                status="failed",
                failure_code="queue_unavailable",
                failure_message="TradingAgents queue is unavailable",
            )
            return _fail("trading_agents_queue_unavailable", 503)
        return _ok({"run_id": run["run_id"], "status": "queued"}, status=202)
    except ValueError as exc:
        return _fail(str(exc), 400)
    except Exception:
        logger.exception("TradingAgents run creation failed")
        return _fail("trading_agents_unavailable", 503)


@trading_agents_blp.route("/runs/<string:run_id>", methods=["GET"])
@login_required
def get_run(run_id: str):
    record = get_repository().get_owned_run(user_id=_user_id(), run_id=run_id)
    if record is None:
        return _fail("trading_agents_run_not_found", 404)
    return _ok(_public_run(record))


@trading_agents_blp.route("/runs/<string:run_id>/events", methods=["GET"])
@login_required
def stream_events(run_id: str):
    try:
        cursor = max(0, int(request.args.get("after", "0")))
    except ValueError:
        return _fail("invalid_event_cursor", 400)
    if get_repository().get_owned_run(user_id=_user_id(), run_id=run_id) is None:
        return _fail("trading_agents_run_not_found", 404)
    user_id = _user_id()

    @stream_with_context
    def generate():
        yield "retry: 1500\n\n"
        last_sequence = cursor
        # A bounded stream leaves polling as the reliable fallback if a proxy
        # closes idle connections. The client reconnects with `after`.
        for _ in range(20):
            record = get_repository().get_owned_run(user_id=user_id, run_id=run_id)
            if record is None:
                return
            for event in record.get("events") or []:
                sequence = int(event.get("sequence") or 0)
                if sequence > last_sequence:
                    yield "event: progress\ndata: {}\n\n".format(json.dumps(event, ensure_ascii=False, default=str))
                    last_sequence = sequence
            status = str(record.get("status") or "queued")
            yield "event: status\ndata: {}\n\n".format(json.dumps({"status": status, "after": last_sequence}))
            if status in _TERMINAL_STATUSES:
                return
            time.sleep(1)

    return Response(generate(), content_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@trading_agents_blp.route("/runs/<string:run_id>/resume", methods=["POST"])
@login_required
def resume_run(run_id: str):
    repository = get_repository()
    record = repository.get_owned_run(user_id=_user_id(), run_id=run_id)
    if record is None:
        return _fail("trading_agents_run_not_found", 404)
    if str(record.get("status")) == "succeeded":
        return _fail("trading_agents_run_already_completed", 409)
    repository.transition_run(run_id=run_id, status="queued")
    enqueue_trading_agents_control(run_id, "resume")
    return _ok({"run_id": run_id, "status": "queued"}, status=202)


@trading_agents_blp.route("/runs/<string:run_id>/cancel", methods=["POST"])
@login_required
def cancel_run(run_id: str):
    repository = get_repository()
    record = repository.get_owned_run(user_id=_user_id(), run_id=run_id)
    if record is None:
        return _fail("trading_agents_run_not_found", 404)
    if str(record.get("status")) != "cancelled":
        repository.transition_run(run_id=run_id, status="cancelled")
        enqueue_trading_agents_control(run_id, "cancel")
    return _ok({"run_id": run_id, "status": "cancelled"}, status=202)


@trading_agents_blp.route("/runs/<string:run_id>/clear-checkpoint", methods=["POST"])
@login_required
def clear_checkpoint(run_id: str):
    if get_repository().get_owned_run(user_id=_user_id(), run_id=run_id) is None:
        return _fail("trading_agents_run_not_found", 404)
    enqueue_trading_agents_control(run_id, "clear-checkpoint")
    return _ok({"run_id": run_id, "checkpoint": "clear_requested"}, status=202)


@trading_agents_blp.route("/runs/<string:run_id>/artifacts/<string:artifact_name>", methods=["GET"])
@login_required
def get_artifact(run_id: str, artifact_name: str):
    record = get_repository().get_owned_run(user_id=_user_id(), run_id=run_id)
    if record is None:
        return _fail("trading_agents_run_not_found", 404)
    artifact = next((item for item in record.get("artifacts") or [] if item.get("artifact_name") == artifact_name), None)
    if artifact is None:
        return _fail("trading_agents_artifact_not_found", 404)
    try:
        content, content_type = fetch_artifact_from_service(run_id=run_id, artifact_name=artifact_name)
    except TradingAgentsServiceUnavailable:
        return _fail("trading_agents_artifact_unavailable", 503)
    return Response(content, content_type=content_type)


__all__ = ["trading_agents_blp"]
