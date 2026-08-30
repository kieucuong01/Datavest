"""Daily OpenBB-Deribit evidence adapter ported from DataVest.

OpenBB stays in an isolated optional virtual environment because its framework
pins conflict with the primary Flask service. The subprocess boundary accepts
and returns bounded JSON only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import subprocess
from typing import Protocol

from .collectors import CollectorUnavailable
from .contracts import Observation
from .sources import source_for_code


_ASSETS = ("BTC", "ETH")
_DAY = Decimal("365")
_UNITS = {
    "crypto.derivatives.futures.near_term_annualized_basis": "return",
    "crypto.derivatives.futures.far_term_annualized_basis": "return",
    "crypto.derivatives.futures.perpetual_close_usd": "USD",
    "crypto.derivatives.futures.perpetual_volume_notional_usd": "USD",
    "crypto.derivatives.options.call_open_interest": "contracts",
    "crypto.derivatives.options.put_open_interest": "contracts",
    "crypto.derivatives.options.put_call_open_interest_ratio": "ratio",
}


class OpenBBDeribitClient(Protocol):
    def collect_daily(self, *, as_of: datetime) -> dict[str, object]: ...


class OpenBBDeribitUnavailable(CollectorUnavailable):
    pass


def _decimal(value: object) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("INVALID_VALUE") from exc
    if not parsed.is_finite():
        raise ValueError("INVALID_VALUE")
    return parsed


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("INVALID_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("INVALID_TIMESTAMP")
    return parsed.astimezone(timezone.utc)


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise ValueError("INVALID_TIMESTAMP")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc


def _records(value: object) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, list) or not value or not all(isinstance(row, Mapping) for row in value):
        raise ValueError("SCHEMA_DRIFT")
    return value


class OpenBBDeribitSubprocessClient:
    def __init__(
        self,
        *,
        python_executable: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.python_executable = python_executable
        self.runner = runner

    def collect_daily(self, *, as_of: datetime) -> dict[str, object]:
        python = self._resolve_python()
        backend_root = Path(__file__).resolve().parents[3]
        script = backend_root / "third_party" / "openbb_deribit_daily.py"
        if not script.is_file():
            raise OpenBBDeribitUnavailable("OPENBB_DERIBIT_UNAVAILABLE")
        try:
            result = self.runner(
                [str(python), str(script), "--as-of", as_of.isoformat()],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise OpenBBDeribitUnavailable("OPENBB_DERIBIT_UNAVAILABLE") from exc
        if result.returncode != 0:
            raise OpenBBDeribitUnavailable("OPENBB_DERIBIT_UNAVAILABLE")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise OpenBBDeribitUnavailable("OPENBB_DERIBIT_UNAVAILABLE") from exc
        if not isinstance(payload, dict):
            raise OpenBBDeribitUnavailable("OPENBB_DERIBIT_UNAVAILABLE")
        return payload

    def _resolve_python(self) -> Path:
        configured = self.python_executable or os.getenv("OPENBB_DERIBIT_PYTHON")
        if configured:
            candidate = Path(configured)
            if candidate.is_file():
                return candidate
        repository_root = Path(__file__).resolve().parents[4]
        candidates = (
            repository_root / ".openbb-deribit-venv" / "Scripts" / "python.exe",
            repository_root / ".openbb-deribit-venv" / "bin" / "python",
            Path("/opt/datavest/shared/openbb-deribit-venv/bin/python"),
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise OpenBBDeribitUnavailable("OPENBB_DERIBIT_UNAVAILABLE")


class OpenBBDeribitCollector:
    def __init__(self, *, client: OpenBBDeribitClient | None = None) -> None:
        self.source = source_for_code("openbb-deribit")
        self.client = client or OpenBBDeribitSubprocessClient()

    def collect(self, as_of: datetime) -> tuple[Observation, ...]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        as_of = as_of.astimezone(timezone.utc)
        effective_at = as_of.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        try:
            payload = self.client.collect_daily(as_of=as_of)
            observed_at = _timestamp(payload.get("observed_at"))
            if observed_at > as_of + timedelta(minutes=5):
                raise ValueError("INVALID_TIMESTAMP")
            return tuple(self._parse(payload, as_of, effective_at, observed_at))
        except OpenBBDeribitUnavailable:
            raise
        except ValueError as exc:
            raise OpenBBDeribitUnavailable(str(exc)) from exc

    def _observation(
        self,
        *,
        metric: str,
        value: Decimal,
        symbol: str,
        dimensions: Mapping[str, str],
        effective_at: datetime,
        observed_at: datetime,
    ) -> Observation:
        return Observation.create(
            source_code=self.source.code,
            source_url=self.source.urls[0],
            market=self.source.market,
            symbol=symbol,
            effective_at=effective_at,
            observed_at=observed_at,
            methodology_version=self.source.methodology_version,
            value={
                "metric": metric,
                "value": str(value),
                "unit": _UNITS[metric],
                "dimensions": dict(dimensions),
                "evidenceOnly": True,
            },
            data_class="LIVE",
        )

    def _parse(
        self,
        payload: Mapping[str, object],
        as_of: datetime,
        effective_at: datetime,
        observed_at: datetime,
    ) -> list[Observation]:
        curves = payload.get("futures_curve")
        historical = payload.get("futures_historical")
        options = payload.get("options_chains")
        if not all(isinstance(value, Mapping) for value in (curves, historical, options)):
            raise ValueError("SCHEMA_DRIFT")
        result: list[Observation] = []
        for asset in _ASSETS:
            result.extend(
                self._curve(asset, _records(curves.get(asset)), as_of, effective_at, observed_at)
            )
            result.extend(
                self._history(asset, _records(historical.get(asset)), effective_at, observed_at)
            )
            result.extend(
                self._options(asset, _records(options.get(asset)), effective_at, observed_at)
            )
        return result

    def _curve(self, asset, rows, as_of, effective_at, observed_at):
        curve_date = as_of.date()
        prices: dict[date, Decimal] = {}
        for row in rows:
            expiration = _date(row.get("expiration"))
            price = _decimal(row.get("price"))
            if price <= 0:
                raise ValueError("INVALID_FUTURES_CURVE")
            if expiration in prices:
                if expiration == curve_date:
                    continue
                raise ValueError("INVALID_FUTURES_CURVE")
            prices[expiration] = price
        perpetual = prices.get(curve_date)
        expiries = sorted(expiry for expiry in prices if expiry > curve_date)
        if perpetual is None or len(expiries) < 2:
            raise ValueError("FUTURES_CURVE_INCOMPLETE")

        def basis(expiration):
            days = (expiration - curve_date).days
            result = ((prices[expiration] / perpetual) - Decimal("1")) * _DAY / Decimal(days)
            if abs(result) > Decimal("5"):
                raise ValueError("INVALID_FUTURES_CURVE")
            return result

        near = expiries[0]
        standard = [expiry for expiry in expiries if (expiry - curve_date).days >= 30]
        far = standard[0] if standard else expiries[-1]
        if far == near:
            far = expiries[-1]
        specs = (
            ("crypto.derivatives.futures.near_term_annualized_basis", near),
            ("crypto.derivatives.futures.far_term_annualized_basis", far),
        )
        return tuple(
            self._observation(
                metric=metric,
                value=basis(expiration),
                symbol=asset,
                dimensions={"frequency": "daily", "tenorDays": str((expiration - curve_date).days)},
                effective_at=effective_at,
                observed_at=observed_at,
            )
            for metric, expiration in specs
        )

    def _history(self, asset, rows, effective_at, observed_at):
        matched = [row for row in rows if _timestamp(row.get("date")).date() == effective_at.date()]
        if len(matched) != 1:
            raise ValueError("FUTURES_HISTORY_INCOMPLETE")
        close = _decimal(matched[0].get("close"))
        volume = _decimal(matched[0].get("volume_notional"))
        if close <= 0 or volume < 0:
            raise ValueError("INVALID_FUTURES_HISTORY")
        dimensions = {"frequency": "daily", "instrument": f"{asset}-PERPETUAL"}
        return tuple(
            self._observation(
                metric=metric,
                value=value,
                symbol=asset,
                dimensions=dimensions,
                effective_at=effective_at,
                observed_at=observed_at,
            )
            for metric, value in (
                ("crypto.derivatives.futures.perpetual_close_usd", close),
                ("crypto.derivatives.futures.perpetual_volume_notional_usd", volume),
            )
        )

    def _options(self, asset, rows, effective_at, observed_at):
        totals = {"call": Decimal("0"), "put": Decimal("0")}
        for row in rows:
            option_type = row.get("option_type")
            if not isinstance(option_type, str) or option_type.casefold() not in totals:
                raise ValueError("INVALID_OPTION_CHAIN")
            amount = _decimal(row.get("open_interest"))
            if amount < 0:
                raise ValueError("INVALID_OPTION_CHAIN")
            totals[option_type.casefold()] += amount
        if totals["call"] <= 0 or totals["put"] <= 0:
            raise ValueError("OPTIONS_COVERAGE_INCOMPLETE")
        dimensions = {"frequency": "daily", "aggregation": "open_interest_sum"}
        values = (
            ("crypto.derivatives.options.call_open_interest", totals["call"]),
            ("crypto.derivatives.options.put_open_interest", totals["put"]),
            ("crypto.derivatives.options.put_call_open_interest_ratio", totals["put"] / totals["call"]),
        )
        return tuple(
            self._observation(
                metric=metric,
                value=value,
                symbol=asset,
                dimensions=dimensions,
                effective_at=effective_at,
                observed_at=observed_at,
            )
            for metric, value in values
        )


__all__ = [
    "OpenBBDeribitCollector",
    "OpenBBDeribitSubprocessClient",
    "OpenBBDeribitUnavailable",
]
