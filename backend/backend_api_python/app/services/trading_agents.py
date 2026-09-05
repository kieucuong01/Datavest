"""Authenticated callback boundary for the private TradingAgents service."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

from flask import Blueprint, jsonify, request

from app.services.trading_agents_repository import TradingAgentsRepository


CALLBACK_TIMESTAMP_HEADER = "X-DataVest-Trading-Agents-Timestamp"
CALLBACK_SIGNATURE_HEADER = "X-DataVest-Trading-Agents-Signature"
MAX_CALLBACK_BYTES = 128 * 1024
MAX_CALLBACK_AGE_SECONDS = 300
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "header",
    "password",
    "secret",
    "token",
    "traceback",
    "stacktrace",
)


class CallbackAuthenticationError(ValueError):
    """Raised when a private service callback is not authentic."""


class CallbackValidationError(ValueError):
    """Raised when an authentic callback does not match the narrow contract."""


class TradingAgentsCallbackService:
    """Validate private callbacks before passing a redacted event to storage."""

    def __init__(
        self,
        *,
        repository: TradingAgentsRepository,
        secret: str,
        now: Callable[[], float] = time.time,
        max_age_seconds: int = MAX_CALLBACK_AGE_SECONDS,
    ) -> None:
        self._repository = repository
        self._secret = str(secret or "")
        self._now = now
        self._max_age_seconds = int(max_age_seconds)
        if len(self._secret.encode("utf-8")) < 16:
            raise ValueError("TradingAgents callback secret must contain at least 16 bytes")

    @classmethod
    def from_environment(cls) -> "TradingAgentsCallbackService":
        secret = os.getenv("DATAVEST_TRADING_AGENTS_CALLBACK_SECRET", "")
        return cls(repository=TradingAgentsRepository(), secret=secret)

    def sign(self, *, timestamp: str, body: bytes) -> str:
        return hmac.new(self._secret.encode("utf-8"), self._signing_bytes(timestamp, body), hashlib.sha256).hexdigest()

    def persist_callback(self, *, headers: Mapping[str, str], raw_body: bytes) -> None:
        if len(raw_body) > MAX_CALLBACK_BYTES:
            raise CallbackValidationError("callback body is too large")
        timestamp = self._header(headers, CALLBACK_TIMESTAMP_HEADER)
        signature = self._header(headers, CALLBACK_SIGNATURE_HEADER)
        self._verify_signature(timestamp=timestamp, signature=signature, body=raw_body)
        try:
            message = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CallbackValidationError("callback body must be JSON") from exc
        if not isinstance(message, dict):
            raise CallbackValidationError("callback body must be an object")

        run_id = self._validate_run_id(message.get("run_id"))
        sequence = self._validate_sequence(message.get("sequence"))
        event_type = self._validate_event_type(message.get("event_type"))
        payload = message.get("payload", {})
        if not isinstance(payload, Mapping):
            raise CallbackValidationError("callback payload must be an object")
        self._repository.append_event(
            run_id=run_id,
            sequence=sequence,
            event_type=event_type,
            payload=redact_callback_payload(payload),
        )
        if event_type == "artifact":
            self._repository.store_artifact(
                run_id=run_id,
                artifact_name=str(payload.get("artifact_name") or ""),
                storage_path=str(payload.get("storage_path") or ""),
                sha256=str(payload.get("sha256") or ""),
                byte_size=payload.get("byte_size", -1),
                content_type=str(payload.get("content_type") or "text/markdown"),
            )
        elif event_type == "run_status":
            self._repository.transition_run(
                run_id=run_id,
                status=str(payload.get("status") or ""),
                failure_code=str(payload.get("failure_code") or "") or None,
                failure_message=str(payload.get("failure_message") or "") or None,
            )

    def _verify_signature(self, *, timestamp: str, signature: str, body: bytes) -> None:
        try:
            timestamp_value = int(timestamp)
        except (TypeError, ValueError) as exc:
            raise CallbackAuthenticationError("missing or invalid callback timestamp") from exc
        if abs(int(self._now()) - timestamp_value) > self._max_age_seconds:
            raise CallbackAuthenticationError("expired callback timestamp")
        expected = self.sign(timestamp=timestamp, body=body)
        if not signature or not hmac.compare_digest(expected, signature):
            raise CallbackAuthenticationError("invalid callback signature")

    @staticmethod
    def _signing_bytes(timestamp: str, body: bytes) -> bytes:
        return str(timestamp).encode("ascii") + b"." + body

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str:
        target = name.lower()
        for key, value in headers.items():
            if str(key).lower() == target:
                return str(value)
        return ""

    @staticmethod
    def _validate_run_id(value: Any) -> str:
        clean_value = str(value or "").strip()
        if not _RUN_ID_RE.fullmatch(clean_value):
            raise CallbackValidationError("invalid run_id")
        return clean_value

    @staticmethod
    def _validate_sequence(value: Any) -> int:
        if isinstance(value, bool):
            raise CallbackValidationError("invalid sequence")
        try:
            clean_value = int(value)
        except (TypeError, ValueError) as exc:
            raise CallbackValidationError("invalid sequence") from exc
        if clean_value <= 0 or clean_value > 2_147_483_647:
            raise CallbackValidationError("invalid sequence")
        return clean_value

    @staticmethod
    def _validate_event_type(value: Any) -> str:
        clean_value = str(value or "").strip().lower()
        if not _EVENT_TYPE_RE.fullmatch(clean_value):
            raise CallbackValidationError("invalid event_type")
        return clean_value


def redact_callback_payload(payload: Mapping[str, Any], *, _depth: int = 0) -> dict[str, Any]:
    """Make callback data safe for durable storage without retaining secrets."""
    if _depth > 8:
        return {"truncated": True}
    cleaned: dict[str, Any] = {}
    for index, (key, value) in enumerate(payload.items()):
        if index >= 100:
            cleaned["truncated"] = True
            break
        key_text = str(key)[:120]
        if _is_sensitive_key(key_text):
            cleaned[key_text] = "[REDACTED]"
        else:
            cleaned[key_text] = _redact_value(value, depth=_depth + 1)
    return cleaned


def _redact_value(value: Any, *, depth: int) -> Any:
    if isinstance(value, Mapping):
        return redact_callback_payload(value, _depth=depth)
    if isinstance(value, list):
        return [_redact_value(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return value[:4096]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:4096]


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def create_internal_callback_blueprint(
    service_factory: Callable[[], TradingAgentsCallbackService] | None = None,
) -> Blueprint:
    """Return the private callback blueprint; Task 6 registers it in the app."""
    factory = service_factory or TradingAgentsCallbackService.from_environment
    blueprint = Blueprint(
        "trading_agents_internal",
        __name__,
        url_prefix="/api/internal/trading-agents",
    )

    @blueprint.post("/callback")
    def callback():
        if request.content_length is not None and request.content_length > MAX_CALLBACK_BYTES:
            return jsonify({"error": {"code": "PAYLOAD_TOO_LARGE"}}), 413
        try:
            factory().persist_callback(headers=request.headers, raw_body=request.get_data(cache=False))
        except CallbackAuthenticationError:
            return jsonify({"error": {"code": "UNAUTHORIZED"}}), 401
        except CallbackValidationError:
            return jsonify({"error": {"code": "INVALID_CALLBACK"}}), 422
        except ValueError:
            return jsonify({"error": {"code": "CALLBACK_UNAVAILABLE"}}), 503
        return jsonify({"accepted": True}), 202

    return blueprint
