"""Build point-in-time Vietnam Evidence snapshots for TradingAgents."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.data_sources import DataSourceFactory
from app.services.market.technical_indicators import calculate_indicators
from app.services.vietnam_evidence import get_vietnam_evidence_service


class TradingAgentsVietnamEvidenceUnavailable(RuntimeError):
    """Raised when a HOSE run cannot obtain safe point-in-time evidence."""


_MAX_AGENT_EVIDENCE_BYTES = 480 * 1024
_OBSERVATIONS_PER_SERIES = 8


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _observation_series(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("itemCode") or row.get("metric") or ""),
        str(row.get("frequency") or ""),
        str(row.get("reportScope") or ""),
        str(row.get("modelType") or ""),
    )


def _observation_order(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("availableAt") or ""),
        str(row.get("periodEnd") or ""),
        str(row.get("itemCode") or ""),
        str(row.get("metric") or ""),
    )


def _compact_agent_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Bound only the private run snapshot; full history remains with its provider."""
    if len(_canonical_json(evidence).encode("utf-8")) <= _MAX_AGENT_EVIDENCE_BYTES:
        return evidence

    fundamentals = evidence.get("fundamentals") or {}
    observations = fundamentals.get("observations") or []
    if not isinstance(fundamentals, dict) or not isinstance(observations, list):
        raise TradingAgentsVietnamEvidenceUnavailable("invalid Vietnam fundamental observations")

    series: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in observations:
        if isinstance(row, dict):
            series.setdefault(_observation_series(row), []).append(row)
    selected = sorted(
        (
            row
            for rows in series.values()
            for row in sorted(rows, key=_observation_order)[-_OBSERVATIONS_PER_SERIES:]
        ),
        key=_observation_order,
    )
    compact = dict(evidence)
    compact["fundamentals"] = {**fundamentals, "observations": selected}
    compact["dataGaps"] = [
        *(evidence.get("dataGaps") or []),
        {"field": "fundamentalStatements", "reason": "AGENT_SNAPSHOT_COMPACTED"},
    ]

    def seal() -> int:
        unsigned = dict(compact)
        unsigned.pop("checksum", None)
        compact["checksum"] = hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()
        return len(_canonical_json(compact).encode("utf-8"))

    byte_size = seal()
    while byte_size > _MAX_AGENT_EVIDENCE_BYTES and selected:
        counts = Counter(_observation_series(row) for row in selected)
        drop_index = next(
            (index for index, row in enumerate(selected) if counts[_observation_series(row)] > 1),
            0,
        )
        selected.pop(drop_index)
        byte_size = seal()
    if byte_size > _MAX_AGENT_EVIDENCE_BYTES:
        raise TradingAgentsVietnamEvidenceUnavailable("Vietnam agent evidence exceeds size limit")
    return compact


def _analysis_cutoff(value: str) -> datetime:
    try:
        analysis_day = date.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise TradingAgentsVietnamEvidenceUnavailable("invalid analysis date") from exc
    local_cutoff = datetime.combine(
        analysis_day,
        time.max,
        tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"),
    )
    return local_cutoff.astimezone(timezone.utc)


def _bar_instant(row: dict[str, Any]) -> datetime | None:
    raw = row.get("time", row.get("timestamp"))
    try:
        number = float(raw)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    if abs(number) > 10_000_000_000:
        number /= 1000.0
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def build_trading_agents_vietnam_evidence(symbol: str, analysis_date: str) -> dict[str, Any]:
    """Build one adjusted, point-in-time Evidence DTO for a HOSE run."""
    cutoff = _analysis_cutoff(analysis_date)
    canonical = str(symbol or "").strip().upper().removesuffix(".VN")
    try:
        raw_rows = DataSourceFactory.get_kline(
            market="VNStock",
            symbol=canonical,
            timeframe="1D",
            limit=260,
            after_time=int((cutoff - timedelta(days=500)).timestamp()),
            before_time=int(cutoff.timestamp()),
            price_mode="adjusted",
        )
    except Exception as exc:
        raise TradingAgentsVietnamEvidenceUnavailable("Vietnam price history unavailable") from exc

    dated_rows = [
        (instant, dict(row))
        for row in (raw_rows or [])
        if isinstance(row, dict)
        and (instant := _bar_instant(row)) is not None
        and instant <= cutoff
    ]
    dated_rows.sort(key=lambda item: item[0])
    rows = [row for _instant, row in dated_rows if float(row.get("close") or 0.0) > 0]
    if not rows:
        raise TradingAgentsVietnamEvidenceUnavailable("Vietnam price history unavailable")

    latest = rows[-1]
    price = {
        "price": float(latest["close"]),
        "open": float(latest.get("open") or latest["close"]),
        "high": float(latest.get("high") or latest["close"]),
        "low": float(latest.get("low") or latest["close"]),
        "volume": float(latest.get("volume") or 0.0),
        "time": latest.get("time", latest.get("timestamp")),
        "timeframe": "1D",
        "source": str(latest.get("source") or "unknown"),
        "priceMode": "adjusted",
    }
    technical = calculate_indicators(rows)
    try:
        evidence = get_vietnam_evidence_service().build(
            symbol=canonical,
            price=price,
            technical=technical,
            as_of=cutoff,
        )
        return _compact_agent_evidence(evidence)
    except Exception as exc:
        raise TradingAgentsVietnamEvidenceUnavailable("Vietnam evidence unavailable") from exc


__all__ = [
    "TradingAgentsVietnamEvidenceUnavailable",
    "build_trading_agents_vietnam_evidence",
]
