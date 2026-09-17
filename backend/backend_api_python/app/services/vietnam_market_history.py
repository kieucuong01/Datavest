"""Canonical Vietnam daily-price selection, quality, and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Iterable


PRICE_MODES = frozenset({"raw", "adjusted", "total_return"})


def normalize_price_mode(value: Any) -> str:
    mode = str(value or "raw").strip().lower().replace("-", "_")
    if mode not in PRICE_MODES:
        raise ValueError("invalid_vietnam_price_mode")
    return mode


@dataclass(frozen=True, slots=True)
class VietnamBarSelection:
    bars: tuple[dict[str, Any], ...]
    canonical_rows: tuple[dict[str, Any], ...]
    provider: str
    coverage: float
    flags: tuple[str, ...]


def _finite_positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _checksum(row: dict[str, Any]) -> str:
    payload = {key: value for key, value in row.items() if key != "checksum"}
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _canonical_row(
    bar: dict[str, Any], *, provider: str, price_mode: str, selected: dict[str, Any]
) -> dict[str, Any]:
    factor = _finite_positive(bar.get("adjustment_factor"))
    row = {
        "time": int(bar["time"]),
        "raw_open": float(bar["open"]),
        "raw_high": float(bar["high"]),
        "raw_low": float(bar["low"]),
        "raw_close": float(bar["close"]),
        "adjusted_open": float(bar["open"]) * factor if factor else None,
        "adjusted_high": float(bar["high"]) * factor if factor else None,
        "adjusted_low": float(bar["low"]) * factor if factor else None,
        "adjusted_close": _finite_positive(bar.get("adjusted_close")),
        "adjustment_factor": factor,
        "volume": float(bar.get("volume") or 0.0),
        "selected_close": float(selected["close"]),
        "price_mode": price_mode,
        "provider": provider,
    }
    row["checksum"] = _checksum(row)
    return row


def select_vietnam_daily_bars(
    provider_results: Iterable[tuple[str, list[dict[str, Any]]]],
    price_mode: str,
) -> VietnamBarSelection:
    mode = normalize_price_mode(price_mode)
    results = [(str(name), list(bars or [])) for name, bars in provider_results if bars]
    if not results:
        return VietnamBarSelection((), (), "", 0.0, ())

    reference = next((bars for name, bars in results if name == "vndirect"), [])
    reference_times = {int(row["time"]) for row in reference}
    flags: list[str] = []

    if mode == "raw":
        provider, source_rows = results[0]
        selected = [dict(row) for row in source_rows]
    else:
        adjusted = next(
            (
                (name, bars)
                for name, bars in results
                if any(_finite_positive(row.get("adjustment_factor")) for row in bars)
            ),
            None,
        )
        if adjusted is None:
            return VietnamBarSelection((), (), "", 0.0, ("adjusted_price_unavailable",))
        provider, source_rows = adjusted
        usable = [
            row for row in source_rows
            if _finite_positive(row.get("adjustment_factor"))
            and float(row.get("volume") or 0.0) > 0
        ]
        if len(usable) != len(source_rows):
            flags.append("invalid_or_zero_volume_removed")
        if reference_times:
            matched = [row for row in usable if int(row["time"]) in reference_times]
            if len(matched) != len(usable):
                flags.append("outside_reference_calendar_removed")
            usable = matched
        selected = []
        for row in usable:
            factor = float(row["adjustment_factor"])
            selected.append({
                "time": int(row["time"]),
                "open": float(row["open"]) * factor,
                "high": float(row["high"]) * factor,
                "low": float(row["low"]) * factor,
                "close": float(row["adjusted_close"]),
                "volume": float(row.get("volume") or 0.0),
                "price_mode": mode,
            })
        flags.append("adjustment_applied")

    by_time = {int(row["time"]): row for row in source_rows}
    canonical = tuple(
        _canonical_row(by_time[int(row["time"])], provider=provider, price_mode=mode, selected=row)
        for row in selected
    )
    denominator = len(reference_times) if reference_times else len(selected)
    coverage = min(1.0, len(selected) / max(denominator, 1)) if selected else 0.0
    return VietnamBarSelection(
        tuple(selected), canonical, provider, coverage, tuple(dict.fromkeys(flags))
    )


class VietnamDailyPriceRepository:
    """Best-effort storage for normalized daily rows selected at runtime."""

    @staticmethod
    def persist(
        *,
        symbol: str,
        price_mode: str,
        provider: str,
        bars: list[dict[str, Any]],
        quality: dict[str, Any],
    ) -> None:
        from app.utils.db import get_db_connection

        observed_at = datetime.now(timezone.utc)
        with get_db_connection() as db:
            cur = db.cursor()
            for row in bars:
                cur.execute(
                    """
                    INSERT INTO qd_vietnam_daily_prices
                      (symbol, trading_time, raw_open, raw_high, raw_low, raw_close,
                       adjusted_open, adjusted_high, adjusted_low, adjusted_close,
                       adjustment_factor, volume, price_mode, source, observed_at,
                       quality_flags, checksum)
                    VALUES (?, to_timestamp(?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?)
                    ON CONFLICT (symbol, trading_time, price_mode, source) DO UPDATE SET
                      raw_open = EXCLUDED.raw_open, raw_high = EXCLUDED.raw_high,
                      raw_low = EXCLUDED.raw_low, raw_close = EXCLUDED.raw_close,
                      adjusted_open = EXCLUDED.adjusted_open,
                      adjusted_high = EXCLUDED.adjusted_high,
                      adjusted_low = EXCLUDED.adjusted_low,
                      adjusted_close = EXCLUDED.adjusted_close,
                      adjustment_factor = EXCLUDED.adjustment_factor,
                      volume = EXCLUDED.volume, observed_at = EXCLUDED.observed_at,
                      quality_flags = EXCLUDED.quality_flags, checksum = EXCLUDED.checksum
                    """,
                    (
                        symbol, row["time"], row["raw_open"], row["raw_high"],
                        row["raw_low"], row["raw_close"], row["adjusted_open"],
                        row["adjusted_high"], row["adjusted_low"], row["adjusted_close"],
                        row["adjustment_factor"], row["volume"], price_mode, provider,
                        observed_at, json.dumps(quality, sort_keys=True), row["checksum"],
                    ),
                )
            db.commit()
            cur.close()


__all__ = [
    "PRICE_MODES", "VietnamBarSelection", "VietnamDailyPriceRepository",
    "normalize_price_mode", "select_vietnam_daily_bars",
]
