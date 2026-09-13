"""Private callback boundary for importing completed browser snapshots."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import hashlib
import hmac
import json
import os
import re
import time

from flask import Blueprint, current_app, jsonify, request


CALLBACK_TIMESTAMP_HEADER = "X-DataVest-Smart-Insights-Timestamp"
CALLBACK_SIGNATURE_HEADER = "X-DataVest-Smart-Insights-Signature"
MAX_CALLBACK_BYTES = 64 * 1024
MAX_CALLBACK_AGE_SECONDS = 5 * 60
MAX_SOURCE_CODES = 64
_SOURCE_CODE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")


class SnapshotImportAuthenticationError(ValueError):
    """The callback did not carry a valid, recent signature."""


class SnapshotImportValidationError(ValueError):
    """The callback body is not a supported snapshot import request."""


def _secret() -> str:
    value = os.getenv("CRYPTO_INSIGHTS_IMPORT_CALLBACK_SECRET", "").strip()
    if len(value.encode("utf-8")) < 16:
        raise ValueError("Smart Insights import callback is unavailable")
    return value


def _header(headers: Mapping[str, str], name: str) -> str:
    target = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == target:
            return str(value)
    return ""


def _verify_signature(*, headers: Mapping[str, str], raw_body: bytes, now: float | None = None) -> None:
    timestamp = _header(headers, CALLBACK_TIMESTAMP_HEADER)
    signature = _header(headers, CALLBACK_SIGNATURE_HEADER)
    try:
        timestamp_value = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise SnapshotImportAuthenticationError("invalid callback timestamp") from exc
    if abs(int(now if now is not None else time.time()) - timestamp_value) > MAX_CALLBACK_AGE_SECONDS:
        raise SnapshotImportAuthenticationError("expired callback timestamp")
    expected = hmac.new(
        _secret().encode("utf-8"),
        timestamp.encode("ascii") + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise SnapshotImportAuthenticationError("invalid callback signature")


def _source_codes(raw_body: bytes) -> tuple[str, ...]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotImportValidationError("callback body must be JSON") from exc
    if not isinstance(payload, dict):
        raise SnapshotImportValidationError("callback body must be an object")
    values = payload.get("sourceCodes")
    if not isinstance(values, list) or not values or len(values) > MAX_SOURCE_CODES:
        raise SnapshotImportValidationError("sourceCodes must be a non-empty list")
    normalized: list[str] = []
    for value in values:
        code = str(value or "").strip().lower()
        if code == "cbbi-public" or not _SOURCE_CODE.fullmatch(code):
            raise SnapshotImportValidationError("unsupported source code")
        if code not in normalized:
            normalized.append(code)
    if not normalized:
        raise SnapshotImportValidationError("no active source codes")
    return tuple(normalized)


def create_internal_snapshot_import_blueprint(
    enqueue_factory: Callable[[Sequence[str]], Mapping[str, object]] | None = None,
) -> Blueprint:
    """Create the HMAC-protected endpoint used only by the browser sidecar."""

    def enqueue(source_codes: Sequence[str]) -> Mapping[str, object]:
        if enqueue_factory is not None:
            return enqueue_factory(source_codes)
        from app.tasks.smart_insights import enqueue_smart_insights_refresh_for_sources

        return enqueue_smart_insights_refresh_for_sources.run(tuple(source_codes))

    blueprint = Blueprint(
        "smart_insights_import_internal",
        __name__,
        url_prefix="/api/internal/smart-insights",
    )

    @blueprint.post("/snapshot-import")
    def snapshot_import():
        if request.content_length is not None and request.content_length > MAX_CALLBACK_BYTES:
            return jsonify({"error": {"code": "PAYLOAD_TOO_LARGE"}}), 413
        raw_body = request.get_data(cache=False)
        if len(raw_body) > MAX_CALLBACK_BYTES:
            return jsonify({"error": {"code": "PAYLOAD_TOO_LARGE"}}), 413
        try:
            _verify_signature(headers=request.headers, raw_body=raw_body)
            source_codes = _source_codes(raw_body)
            result = enqueue(source_codes)
        except SnapshotImportAuthenticationError:
            return jsonify({"error": {"code": "UNAUTHORIZED"}}), 401
        except SnapshotImportValidationError:
            return jsonify({"error": {"code": "INVALID_CALLBACK"}}), 422
        except ValueError:
            return jsonify({"error": {"code": "CALLBACK_UNAVAILABLE"}}), 503
        except Exception:
            current_app.logger.exception("smart insights snapshot import callback failed")
            return jsonify({"error": {"code": "CALLBACK_UNAVAILABLE"}}), 503

        queued = bool(result.get("queued")) if isinstance(result, Mapping) else True
        return jsonify({"accepted": True, "queued": queued, "sourceCount": len(source_codes)}), 202

    return blueprint


__all__ = [
    "CALLBACK_SIGNATURE_HEADER",
    "CALLBACK_TIMESTAMP_HEADER",
    "create_internal_snapshot_import_blueprint",
]
