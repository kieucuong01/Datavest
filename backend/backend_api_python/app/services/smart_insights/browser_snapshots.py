"""Validated, atomic local snapshots for Browser Use crypto collectors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping


DEFAULT_ROOT = "data/crypto-insights"
_CRYPTOETF_SNAPSHOT_SOURCES = (
    "cryptoetf-btc-etf", "cryptoetf-eth-etf", "cryptoetf-sol-etf", "cryptoetf-xrp-etf",
    "cryptoetf-hyp-etf", "cryptoetf-doge-etf", "cryptoetf-link-etf", "cryptoetf-avax-etf",
    "cryptoetf-hbar-etf", "cryptoetf-ltc-etf", "cryptoetf-bnb-etf", "cryptoetf-dot-etf",
    "cryptoetf-sui-etf",
)
_STALE_AFTER = {
    "alternative-fng": timedelta(days=2),
    "farside-btc-etf": timedelta(days=2),
    "farside-eth-etf": timedelta(days=2),
    "farside-sol-etf": timedelta(days=2),
    **{source: timedelta(days=2) for source in _CRYPTOETF_SNAPSHOT_SOURCES},
    "xoomar-btc-etf": timedelta(days=2),
    "xoomar-eth-etf": timedelta(days=2),
    "blockchaincenter-altcoin-season": timedelta(days=2),
    "coinshares-weekly": timedelta(days=9),
    "bitinfocharts-top-addresses": timedelta(days=2),
}


class SnapshotUnavailable(RuntimeError):
    """A snapshot is missing, invalid, or too old to import."""


def snapshot_root() -> Path:
    return Path(os.getenv("CRYPTO_INSIGHTS_SNAPSHOT_ROOT", DEFAULT_ROOT)).expanduser()


def _parse_time(value: object, *, error: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise SnapshotUnavailable(error) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SnapshotUnavailable(error)
    return parsed.astimezone(timezone.utc)


def _validate_number(value: object) -> None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SnapshotUnavailable("INVALID_VALUE") from exc
    if not parsed.is_finite():
        raise SnapshotUnavailable("INVALID_VALUE")


def validate_snapshot(source_code: str, payload: Mapping[str, object], *, now: datetime | None = None) -> None:
    if source_code not in _STALE_AFTER:
        raise SnapshotUnavailable("UNKNOWN_SOURCE")
    if str(payload.get("source", "")).strip() != source_code:
        raise SnapshotUnavailable("SOURCE_IDENTITY_MISMATCH")
    if not str(payload.get("source_url", "")).strip():
        raise SnapshotUnavailable("MISSING_SOURCE_URL")
    if payload.get("schema_version") != 1:
        raise SnapshotUnavailable("SCHEMA_VERSION")
    fetched_at = _parse_time(payload.get("fetched_at"), error="INVALID_FETCHED_AT")
    if now is not None:
        current = now.astimezone(timezone.utc)
        if fetched_at > current + timedelta(minutes=5):
            raise SnapshotUnavailable("INVALID_FETCHED_AT")
        if current - fetched_at > _STALE_AFTER[source_code]:
            raise SnapshotUnavailable("STALE_SNAPSHOT")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise SnapshotUnavailable("REQUIRED_RECORDS")
    coverage = payload.get("coverage")
    if not isinstance(coverage, Mapping) or coverage.get("record_count") != len(records):
        raise SnapshotUnavailable("INVALID_COVERAGE")
    for record in records:
        if not isinstance(record, Mapping):
            raise SnapshotUnavailable("INVALID_RECORD")
        _parse_time(record.get("effective_at"), error="INVALID_EFFECTIVE_AT")
        if not str(record.get("metric", "")).strip() or not str(record.get("unit", "")).strip():
            raise SnapshotUnavailable("INVALID_RECORD")
        _validate_number(record.get("value"))


def write_snapshot(source_code: str, payload: Mapping[str, object], *, root: Path | None = None) -> Path:
    """Validate first, then replace one source file atomically."""
    validate_snapshot(source_code, payload)
    target_root = root or snapshot_root()
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / f"{source_code}.json"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target_root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        Path(temporary_name).replace(target)
    finally:
        Path(temporary_name).unlink(missing_ok=True)
    return target


def load_snapshot(source_code: str, *, root: Path | None = None, now: datetime | None = None) -> Mapping[str, object]:
    target = (root or snapshot_root()) / f"{source_code}.json"
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotUnavailable("MISSING_OR_INVALID_SNAPSHOT") from exc
    if not isinstance(payload, Mapping):
        raise SnapshotUnavailable("MISSING_OR_INVALID_SNAPSHOT")
    validate_snapshot(source_code, payload, now=now)
    return payload


__all__ = ["SnapshotUnavailable", "load_snapshot", "snapshot_root", "validate_snapshot", "write_snapshot"]
