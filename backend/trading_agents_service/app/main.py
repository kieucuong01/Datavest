"""Private HTTP surface for the TradingAgents runtime.

This module intentionally does not import the vendored graph. Runtime settings
are validated first by the ASGI factory; graph construction begins in Task 3.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Request as FastAPIRequest, Response

from .config import Settings, load_settings
from .instruments import resolve_instrument
from .reporting import ReportArtifactError, read_native_report
from .runner import RunCancelled, TradingAgentsRunRequest, clear_native_checkpoint, run_full_graph
from .state import resolve_user_state


_REQUEST_TIMESTAMP_HEADER = "x-datavest-trading-agents-request-timestamp"
_REQUEST_SIGNATURE_HEADER = "x-datavest-trading-agents-request-signature"
_CALLBACK_TIMESTAMP_HEADER = "X-DataVest-Trading-Agents-Timestamp"
_CALLBACK_SIGNATURE_HEADER = "X-DataVest-Trading-Agents-Signature"
_MAX_AGE_SECONDS = 300


@dataclass
class _ActiveRun:
    cancelled: threading.Event


def _signature(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()


def _verify_private_request(settings: Settings, request: FastAPIRequest, body: bytes) -> None:
    timestamp = request.headers.get(_REQUEST_TIMESTAMP_HEADER, "")
    signature = request.headers.get(_REQUEST_SIGNATURE_HEADER, "")
    try:
        timestamp_number = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="unauthorized") from exc
    if abs(int(time.time()) - timestamp_number) > _MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="unauthorized")
    expected = _signature(settings.service_secret, timestamp, body)
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="unauthorized")


def _callback(settings: Settings, message: Mapping[str, Any]) -> None:
    body = json.dumps(dict(message), ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    timestamp = str(int(time.time()))
    request = Request(
        settings.callback_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            _CALLBACK_TIMESTAMP_HEADER: timestamp,
            _CALLBACK_SIGNATURE_HEADER: _signature(settings.callback_secret, timestamp, body),
        },
    )
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed operator callback URL
            response.read(8 * 1024)
    except (HTTPError, URLError, TimeoutError, OSError):
        # The run files remain in the scoped volume for an operator retry. Do
        # not expose the callback endpoint or exception detail to clients.
        return


def _run_payload(payload: Mapping[str, Any]) -> TradingAgentsRunRequest:
    run_id = str(payload.get("run_id") or "")
    user_id = str(payload.get("user_id") or "")
    market = str(payload.get("market") or "")
    symbol = str(payload.get("symbol") or "")
    ticker, asset_type = resolve_instrument(market, symbol)
    selected = tuple(payload.get("selected_analysts") or ())
    native_config = payload.get("native_config") or {}
    if not isinstance(native_config, Mapping):
        raise ValueError("native_config must be an object")
    return TradingAgentsRunRequest(
        run_id=run_id,
        user_id=user_id,
        ticker=ticker,
        asset_type=asset_type,
        analysis_date=str(payload.get("analysis_date") or ""),
        selected_analysts=selected,
        native_config=native_config,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the private service after validating container-only settings."""

    runtime_settings = settings or load_settings()
    app = FastAPI(
        title="DataVest TradingAgents Service",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    active_runs: dict[str, _ActiveRun] = {}
    active_lock = threading.Lock()

    async def verified_payload(request: FastAPIRequest) -> dict[str, Any]:
        body = await request.body()
        _verify_private_request(runtime_settings, request, body)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail="invalid_request") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="invalid_request")
        return payload

    def graph_request_for(payload: Mapping[str, Any], *, expected_run_id: str | None = None) -> TradingAgentsRunRequest:
        try:
            graph_request = _run_payload(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid_request") from exc
        if expected_run_id is not None and graph_request.run_id != expected_run_id:
            raise HTTPException(status_code=422, detail="invalid_request")
        return graph_request

    def submit(graph_request: TradingAgentsRunRequest) -> bool:
        with active_lock:
            if graph_request.run_id in active_runs:
                return False
            active = _ActiveRun(cancelled=threading.Event())
            active_runs[graph_request.run_id] = active

        def execute() -> None:
            sequence = 0

            def publish(event_type: str, event_payload: Mapping[str, Any]) -> None:
                nonlocal sequence
                sequence += 1
                _callback(runtime_settings, {
                    "run_id": graph_request.run_id,
                    "sequence": sequence,
                    "event_type": event_type,
                    "payload": dict(event_payload),
                })

            try:
                result = run_full_graph(
                    graph_request,
                    state_root=runtime_settings.state_root,
                    on_event=lambda event: publish(event.kind, event.payload),
                    should_cancel=active.cancelled.is_set,
                )
                for tool_event in result.tool_events:
                    publish("tool", tool_event.__dict__)
                publish("artifact", {
                    "artifact_name": result.artifact.path.name,
                    "storage_path": f"runs/{graph_request.run_id}/{result.artifact.path.name}",
                    "sha256": result.artifact.sha256,
                    "byte_size": result.artifact.size_bytes,
                    "content_type": "text/markdown",
                })
                publish("run_status", {"status": "succeeded"})
            except RunCancelled:
                publish("run_status", {"status": "cancelled"})
            except Exception:
                publish("run_status", {"status": "failed", "failure_code": "runner_failed"})
            finally:
                with active_lock:
                    if active_runs.get(graph_request.run_id) is active:
                        active_runs.pop(graph_request.run_id, None)

        threading.Thread(target=execute, name=f"trading-agents-{graph_request.run_id[:12]}", daemon=True).start()
        return True

    @app.get("/internal/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "trading-agents",
        }

    @app.post("/internal/runs", include_in_schema=False, status_code=202)
    async def start_run(request: FastAPIRequest) -> dict[str, Any]:
        payload = await verified_payload(request)
        graph_request = graph_request_for(payload)
        submit(graph_request)
        return {"accepted": True, "run_id": graph_request.run_id}

    @app.post("/internal/runs/{run_id}/resume", include_in_schema=False, status_code=202)
    async def resume_run(run_id: str, request: FastAPIRequest) -> dict[str, Any]:
        payload = await verified_payload(request)
        graph_request = graph_request_for(payload, expected_run_id=run_id)
        accepted = submit(graph_request)
        return {
            "accepted": True,
            "run_id": graph_request.run_id,
            "status": "resuming" if accepted else "already_running",
        }

    @app.post("/internal/runs/{run_id}/cancel", include_in_schema=False, status_code=202)
    async def cancel_run(run_id: str, request: FastAPIRequest) -> dict[str, Any]:
        payload = await verified_payload(request)
        graph_request = graph_request_for(payload, expected_run_id=run_id)
        with active_lock:
            active = active_runs.get(graph_request.run_id)
            if active is not None:
                active.cancelled.set()
        return {
            "accepted": True,
            "run_id": graph_request.run_id,
            "status": "cancellation_requested" if active is not None else "not_running",
        }

    @app.post("/internal/runs/{run_id}/clear-checkpoint", include_in_schema=False, status_code=202)
    async def clear_checkpoint(run_id: str, request: FastAPIRequest) -> dict[str, Any]:
        payload = await verified_payload(request)
        graph_request = graph_request_for(payload, expected_run_id=run_id)
        with active_lock:
            if graph_request.run_id in active_runs:
                raise HTTPException(status_code=409, detail="run_active")
        clear_native_checkpoint(graph_request, state_root=runtime_settings.state_root)
        return {"accepted": True, "run_id": graph_request.run_id, "status": "checkpoint_cleared"}

    @app.post("/internal/artifacts", include_in_schema=False)
    async def read_artifact(request: FastAPIRequest) -> Response:
        payload = await verified_payload(request)
        try:
            user_id = str(payload.get("user_id") or "")
            run_id = str(payload.get("run_id") or "")
            artifact_name = str(payload.get("artifact_name") or "")
            paths = resolve_user_state(runtime_settings.state_root, user_id)
            content, content_type = read_native_report(
                paths=paths,
                run_id=run_id,
                artifact_name=artifact_name,
            )
        except (ValueError, ReportArtifactError) as exc:
            raise HTTPException(status_code=422, detail="artifact_unavailable") from exc
        return Response(content, media_type=content_type)

    return app
