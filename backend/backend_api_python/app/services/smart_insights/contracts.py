"""Source-backed Smart Insights contracts ported from DataVest.

The original DataVest worker contracts were adapted from organization UUIDs to
QuantDinger's integer ``user_id`` ownership and a strict LIVE/DEMO boundary.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Mapping
from urllib.parse import parse_qsl, urlsplit


_SENSITIVE_QUERY_KEYS = {
    "api_key",
    "apikey",
    "key",
    "secret",
    "token",
    "access_token",
    "authorization",
}


class DataClass(StrEnum):
    LIVE = "LIVE"
    DEMO = "DEMO"


class EvidencePolicyError(ValueError):
    """Raised when evidence cannot enter a production calculation."""


def _aware_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _safe_https_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Source URL must use HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("Source URL must not contain credentials")
    if any(key.lower() in _SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parsed.query)):
        raise ValueError("Source URL must not contain credentials")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True, slots=True)
class Observation:
    source_code: str
    source_url: str
    market: str
    effective_at: datetime
    observed_at: datetime
    methodology_version: str
    value: Mapping[str, object]
    warnings: tuple[str, ...]
    data_class: DataClass
    checksum: str
    published_at: datetime | None = None
    symbol: str | None = None

    @classmethod
    def create(
        cls,
        *,
        source_code: str,
        source_url: str,
        market: str,
        effective_at: datetime,
        observed_at: datetime,
        methodology_version: str,
        value: Mapping[str, object],
        data_class: DataClass | str,
        warnings: tuple[str, ...] = (),
        published_at: datetime | None = None,
        symbol: str | None = None,
    ) -> "Observation":
        if not source_code.strip() or not market.strip() or not methodology_version.strip():
            raise ValueError("Observation identity and methodology are required")
        if not isinstance(value, Mapping) or not value:
            raise ValueError("Observation value is required")
        normalized_class = DataClass(str(data_class).upper())
        effective_utc = _aware_utc(effective_at, "effective_at")
        observed_utc = _aware_utc(observed_at, "observed_at")
        published_utc = _aware_utc(published_at, "published_at") if published_at else None
        safe_url = _safe_https_url(source_url)
        normalized_warnings = tuple(str(item) for item in warnings)
        checksum_payload = {
            "sourceCode": source_code.strip(),
            "sourceUrl": safe_url,
            "market": market.strip().lower(),
            "symbol": symbol.strip().upper() if symbol else None,
            "effectiveAt": effective_utc.isoformat(),
            "publishedAt": published_utc.isoformat() if published_utc else None,
            "methodologyVersion": methodology_version.strip(),
            "value": value,
            "warnings": normalized_warnings,
            "dataClass": normalized_class.value,
        }
        checksum = hashlib.sha256(_canonical_json(checksum_payload).encode("utf-8")).hexdigest()
        return cls(
            source_code=source_code.strip(),
            source_url=safe_url,
            market=market.strip().lower(),
            symbol=symbol.strip().upper() if symbol else None,
            effective_at=effective_utc,
            published_at=published_utc,
            observed_at=observed_utc,
            methodology_version=methodology_version.strip(),
            value=dict(value),
            warnings=normalized_warnings,
            data_class=normalized_class,
            checksum=checksum,
        )

    def provenance(self) -> dict[str, object]:
        return {
            "source": self.source_code,
            "sourceUrl": self.source_url,
            "effectiveAt": self.effective_at.isoformat(),
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
            "observedAt": self.observed_at.isoformat(),
            "methodologyVersion": self.methodology_version,
            "warnings": list(self.warnings),
            "checksum": self.checksum,
            "dataClass": self.data_class.value,
        }
