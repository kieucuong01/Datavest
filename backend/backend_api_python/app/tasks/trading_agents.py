"""Celery dispatchers for the private, full TradingAgents runtime."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from app.celery_app import celery_app


REQUEST_TIMESTAMP_HEADER = "X-DataVest-Trading-Agents-Request-Timestamp"
REQUEST_SIGNATURE_HEADER = "X-DataVest-Trading-Agents-Request-Signature"
_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


class TradingAgentsServiceUnavailable(RuntimeError):
    """Private service is unavailable or rejected a signed request."""


class TradingAgentsServiceRejected(TradingAgentsServiceUnavailable):
    """The trusted service declined a valid request without being unavailable."""


def get_repository():
    from app.services.trading_agents_repository import TradingAgentsRepository

    return TradingAgentsRepository()


def _service_secret() -> str:
    value = os.getenv("DATAVEST_TRADING_AGENTS_SERVICE_SECRET", "").strip()
    if len(value.encode("utf-8")) < 16:
        raise TradingAgentsServiceUnavailable("TradingAgents private service is unavailable")
    return value


def _service_url() -> str:
    value = os.getenv("DATAVEST_TRADING_AGENTS_SERVICE_URL", "http://trading-agents:8080").strip()
    if not value.startswith(("http://", "https://")):
        raise TradingAgentsServiceUnavailable("TradingAgents private service is unavailable")
    return value.rstrip("/") + "/"


def _service_timeout() -> int:
    try:
        return min(3600, max(5, int(os.getenv("DATAVEST_TRADING_AGENTS_SERVICE_TIMEOUT_SEC", "3300"))))
    except ValueError:
        return 3300


def _signature(secret: str, *, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), f"{timestamp}.".encode("ascii") + body, hashlib.sha256).hexdigest()


def _signed_headers(secret: str, *, body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    return {
        "Content-Type": "application/json",
        REQUEST_TIMESTAMP_HEADER: timestamp,
        REQUEST_SIGNATURE_HEADER: _signature(secret, timestamp=timestamp, body=body),
    }


def post_to_service(*, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Send a signed JSON request without logging body, headers or secrets."""
    secret = _service_secret()
    body = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request = Request(
        urljoin(_service_url(), path.lstrip("/")),
        data=body,
        headers=_signed_headers(secret, body=body),
        method="POST",
    )
    try:
        with urlopen(request, timeout=_service_timeout()) as response:  # noqa: S310 - fixed operator URL, not user input
            response_body = response.read(128 * 1024)
    except HTTPError as exc:
        if exc.code in {400, 401, 409, 422}:
            raise TradingAgentsServiceRejected("TradingAgents private service rejected the request") from exc
        raise TradingAgentsServiceUnavailable("TradingAgents private service is unavailable") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TradingAgentsServiceUnavailable("TradingAgents private service is unavailable") from exc
    try:
        parsed = json.loads(response_body.decode("utf-8")) if response_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TradingAgentsServiceUnavailable("TradingAgents private service returned an invalid response") from exc
    return parsed if isinstance(parsed, dict) else {}


def fetch_artifact_from_service(*, user_id: int, run_id: str, artifact_name: str) -> tuple[bytes, str]:
    """Retrieve one approved artifact through the same signed private boundary."""
    secret = _service_secret()
    body = json.dumps(
        {"user_id": str(int(user_id)), "run_id": str(run_id), "artifact_name": str(artifact_name)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    request = Request(
        urljoin(_service_url(), "internal/artifacts"),
        data=body,
        headers=_signed_headers(secret, body=body),
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed operator URL, not user input
            return response.read(4 * 1024 * 1024), str(response.headers.get_content_type() or "text/plain")
    except HTTPError as exc:
        if exc.code in {400, 401, 404, 409, 422}:
            raise TradingAgentsServiceRejected("TradingAgents artifact is unavailable") from exc
        raise TradingAgentsServiceUnavailable("TradingAgents artifact is unavailable") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TradingAgentsServiceUnavailable("TradingAgents artifact is unavailable") from exc


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _service_run_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    request = _json_object(record.get("request_json"))
    config = _json_object(record.get("config_json"))
    return {
        "run_id": str(record["run_id"]),
        "user_id": str(record["user_id"]),
        "market": str(request.get("market") or ""),
        "symbol": str(request.get("symbol") or ""),
        "analysis_date": str(request.get("analysis_date") or ""),
        "native_config": config.get("native_config") or {},
        "selected_analysts": config.get("selected_analysts") or [],
    }


@celery_app.task(name="datavest.tasks.trading_agents_run", acks_late=True)
def execute_trading_agents_run(run_id: str) -> None:
    repository = get_repository()
    record = repository.get_run_for_worker(run_id=str(run_id))
    if not record or str(record.get("status")) in _TERMINAL_STATUSES:
        return
    try:
        repository.transition_run(run_id=str(run_id), status="running")
        post_to_service(path="/internal/runs", payload=_service_run_payload(record))
    except TradingAgentsServiceRejected:
        repository.transition_run(
            run_id=str(run_id),
            status="failed",
            failure_code="service_rejected",
            failure_message="TradingAgents private service rejected the run",
        )
    except TradingAgentsServiceUnavailable:
        repository.transition_run(
            run_id=str(run_id),
            status="failed",
            failure_code="service_unavailable",
            failure_message="TradingAgents private service is unavailable",
        )


@celery_app.task(name="datavest.tasks.trading_agents_control", acks_late=True)
def execute_trading_agents_control(run_id: str, action: str) -> None:
    repository = get_repository()
    record = repository.get_run_for_worker(run_id=str(run_id))
    if not record:
        return
    clean_action = str(action or "").strip().lower()
    if clean_action not in {"resume", "cancel", "clear-checkpoint"}:
        return
    if clean_action == "cancel":
        repository.transition_run(run_id=str(run_id), status="cancelled")
    try:
        post_to_service(
            path=f"/internal/runs/{quote(str(run_id), safe='')}/{clean_action}",
            payload=_service_run_payload(record),
        )
    except TradingAgentsServiceRejected:
        return
    except TradingAgentsServiceUnavailable:
        if clean_action != "cancel":
            repository.transition_run(
                run_id=str(run_id),
                status="failed",
                failure_code="service_unavailable",
                failure_message="TradingAgents private service is unavailable",
            )


def enqueue_trading_agents_run(run_id: str):
    return execute_trading_agents_run.delay(str(run_id))


def enqueue_trading_agents_control(run_id: str, action: str):
    return execute_trading_agents_control.delay(str(run_id), str(action))
