"""Build point-in-time Vietnam Evidence snapshots for TradingAgents."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.data_sources import DataSourceFactory
from app.services.market.technical_indicators import calculate_indicators
from app.services.vietnam_evidence import get_vietnam_evidence_service


class TradingAgentsVietnamEvidenceUnavailable(RuntimeError):
    """Raised when a HOSE run cannot obtain safe point-in-time evidence."""


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
        "source": str(latest.get("source") or "vndirect+yahoo"),
        "priceMode": "adjusted",
    }
    technical = calculate_indicators(rows)
    try:
        return get_vietnam_evidence_service().build(
            symbol=canonical,
            price=price,
            technical=technical,
            as_of=cutoff,
        )
    except Exception as exc:
        raise TradingAgentsVietnamEvidenceUnavailable("Vietnam evidence unavailable") from exc


__all__ = [
    "TradingAgentsVietnamEvidenceUnavailable",
    "build_trading_agents_vietnam_evidence",
]
