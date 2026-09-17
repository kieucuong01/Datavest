"""Validation and prompt-safe projection of DataVest Vietnam Evidence DTOs."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo


_CHECKSUM_RE = re.compile(r"^[a-f0-9]{64}$")
_MAX_EVIDENCE_BYTES = 512 * 1024
_MAX_CONTEXT_CHARS = 12_000


class VietnamEvidenceValidationError(ValueError):
    """Raised when a signed service request contains invalid HOSE evidence."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _instant(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cutoff(analysis_date: str) -> datetime:
    try:
        day = date.fromisoformat(str(analysis_date or ""))
    except ValueError as exc:
        raise VietnamEvidenceValidationError("invalid evidence cutoff") from exc
    return datetime.combine(day, time.max, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")).astimezone(timezone.utc)


def validate_vietnam_evidence(
    evidence: Mapping[str, Any],
    *,
    ticker: str,
    analysis_date: str,
) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise VietnamEvidenceValidationError("Vietnam evidence must be an object")
    normalized = dict(evidence)
    serialized = _canonical_json(normalized)
    if len(serialized.encode("utf-8")) > _MAX_EVIDENCE_BYTES:
        raise VietnamEvidenceValidationError("Vietnam evidence is too large")
    supplied_checksum = str(normalized.pop("checksum", "")).lower()
    if not _CHECKSUM_RE.fullmatch(supplied_checksum):
        raise VietnamEvidenceValidationError("Vietnam evidence checksum is invalid")
    computed_checksum = hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(supplied_checksum, computed_checksum):
        raise VietnamEvidenceValidationError("Vietnam evidence checksum mismatch")
    if normalized.get("version") != "vietnam-evidence-v1":
        raise VietnamEvidenceValidationError("unsupported Vietnam evidence version")

    instrument = normalized.get("instrument")
    if not isinstance(instrument, Mapping):
        raise VietnamEvidenceValidationError("Vietnam evidence instrument is invalid")
    expected_symbol = str(ticker or "").strip().upper().removesuffix(".VN")
    actual_symbol = str(instrument.get("symbol") or "").strip().upper()
    if actual_symbol != expected_symbol:
        raise VietnamEvidenceValidationError("Vietnam evidence symbol mismatch")
    if instrument.get("market") != "VNStock" or instrument.get("exchange") != "HOSE":
        raise VietnamEvidenceValidationError("Vietnam evidence instrument is not HOSE")

    as_of = _instant(normalized.get("asOf"))
    cutoff = _cutoff(analysis_date)
    if as_of is None or as_of > cutoff:
        raise VietnamEvidenceValidationError("Vietnam evidence exceeds analysis cutoff")
    price = normalized.get("price")
    if not isinstance(price, Mapping):
        raise VietnamEvidenceValidationError("Vietnam evidence price is missing")
    try:
        last_price = float(price.get("price") or 0.0)
    except (TypeError, ValueError):
        last_price = 0.0
    if last_price <= 0:
        raise VietnamEvidenceValidationError("Vietnam evidence price is missing")

    fundamentals = normalized.get("fundamentals") or {}
    if not isinstance(fundamentals, Mapping):
        raise VietnamEvidenceValidationError("Vietnam evidence fundamentals are invalid")
    observations = fundamentals.get("observations") or []
    corporate_actions = normalized.get("corporateActions") or []
    disclosures = normalized.get("disclosures") or []
    for field_name, rows in (
        ("fundamental observations", observations),
        ("corporate actions", corporate_actions),
        ("disclosures", disclosures),
    ):
        if not isinstance(rows, list):
            raise VietnamEvidenceValidationError(f"Vietnam evidence {field_name} are invalid")

    dated_rows = [*observations, *corporate_actions, *disclosures]
    for row in dated_rows:
        if not isinstance(row, Mapping):
            continue
        available_at = _instant(row.get("availableAt"))
        if available_at is not None and available_at > cutoff:
            raise VietnamEvidenceValidationError("Vietnam evidence contains data after cutoff")

    normalized["checksum"] = supplied_checksum
    return normalized


def _bounded(value: Any, *, depth: int = 0) -> Any:
    if depth >= 5:
        return "[truncated]"
    if isinstance(value, Mapping):
        return {
            str(key)[:80]: _bounded(item, depth=depth + 1)
            for key, item in list(value.items())[:40]
        }
    if isinstance(value, list):
        return [_bounded(item, depth=depth + 1) for item in value[:20]]
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


def _recent(rows: Any, limit: int) -> list[Any]:
    values = [dict(row) for row in (rows or []) if isinstance(row, Mapping)]
    values.sort(key=lambda row: (str(row.get("availableAt") or ""), str(row.get("periodEnd") or "")))
    return values[-limit:]


def format_vietnam_evidence_context(evidence: Mapping[str, Any]) -> str:
    fundamentals = evidence.get("fundamentals") if isinstance(evidence.get("fundamentals"), Mapping) else {}
    compact = {
        "version": evidence.get("version"),
        "checksum": evidence.get("checksum"),
        "asOf": evidence.get("asOf"),
        "instrument": evidence.get("instrument") or {},
        "price": evidence.get("price") or {},
        "technical": evidence.get("technical") or {},
        "fundamentals": {
            "derivedMetrics": fundamentals.get("derivedMetrics") or {},
            "observations": _recent(fundamentals.get("observations"), 12),
        },
        "corporateActions": _recent(evidence.get("corporateActions"), 8),
        "disclosures": _recent(evidence.get("disclosures"), 8),
        "marketContext": evidence.get("marketContext") or {},
        "dataGaps": evidence.get("dataGaps") or [],
        "sources": evidence.get("sources") or [],
    }
    compact = _bounded(compact)
    prefix = (
        "DATAVEST_VIETNAM_EVIDENCE: The following DataVest snapshot is the authoritative "
        "point-in-time source for exact HOSE identity, price, technical, fundamental, corporate-action, "
        "disclosure, and Vietnam market-context claims. Generic tools may only supplement it with data "
        "dated no later than the analysis date. Disclose conflicts and data gaps; never fabricate missing values. "
    )
    payload = _canonical_json(compact)
    context = prefix + payload
    if len(context) > _MAX_CONTEXT_CHARS:
        compact["fundamentals"]["observations"] = []
        compact["corporateActions"] = []
        compact["disclosures"] = []
        payload = _canonical_json(compact)
        context = prefix + payload
    if len(context) > _MAX_CONTEXT_CHARS:
        compact["technical"] = {"truncated": True}
        compact["marketContext"] = {"truncated": True}
        context = prefix + _canonical_json(compact)
    return context[:_MAX_CONTEXT_CHARS]


def evidence_provenance(evidence: Mapping[str, Any]) -> dict[str, Any]:
    providers = []
    for source in evidence.get("sources") or []:
        provider = str(source.get("provider") or "") if isinstance(source, Mapping) else ""
        if provider and provider not in providers:
            providers.append(provider)
    return {
        "version": str(evidence.get("version") or ""),
        "checksum": str(evidence.get("checksum") or ""),
        "asOf": str(evidence.get("asOf") or ""),
        "providers": providers,
        "gapCount": len(evidence.get("dataGaps") or []),
    }


__all__ = [
    "VietnamEvidenceValidationError",
    "evidence_provenance",
    "format_vietnam_evidence_context",
    "validate_vietnam_evidence",
]
