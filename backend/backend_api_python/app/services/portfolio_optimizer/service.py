"""Portfolio optimizer orchestration with LIVE-only data and paper-only apply."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from hashlib import sha256
import json
from typing import Any

import numpy as np

from app.utils.supported_markets import canonicalize_supported_symbol

from .engine import OptimizerInput, optimize
from .market_data import Instrument, MarketDataGateway, PriceSeries


_MARKETS = {
    "crypto": "Crypto",
    "us": "USStock",
    "usstock": "USStock",
    "vn": "VNStock",
    "vnstock": "VNStock",
    "gold": "Forex",
    "xau": "Forex",
    "forex": "Forex",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _checksum(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _series_dict(series: PriceSeries) -> dict[str, Any]:
    return {
        "market": series.market,
        "symbol": series.symbol,
        "currency": series.currency,
        "timestamps": list(series.timestamps),
        "closes": list(series.closes),
        "provider": series.provider,
        "fallbackChain": list(series.fallback_chain),
        "coverage": series.coverage,
        "checksum": series.checksum,
        "dataClass": series.data_class,
        "priceUnit": series.price_unit or series.currency,
        "markToMarketSupported": series.mark_to_market_supported,
    }


def _validate_series(series: PriceSeries) -> None:
    if series.data_class != "LIVE":
        raise ValueError("live_market_data_required")
    if not series.provider.strip():
        raise ValueError("provider_provenance_required")
    if not series.checksum.strip():
        raise ValueError("market_data_checksum_required")
    if not 0 < float(series.coverage) <= 1:
        raise ValueError("market_data_coverage_required")
    if len(series.timestamps) != len(series.closes) or len(set(series.timestamps)) != len(series.timestamps):
        raise ValueError("invalid_market_data_series")
    if any(not np.isfinite(value) or value <= 0 for value in series.closes):
        raise ValueError("invalid_market_data_series")


class PortfolioOptimizerService:
    def __init__(self, *, repository=None, gateway: MarketDataGateway | None = None) -> None:
        if repository is None:
            from .repository import PortfolioOptimizerRepository

            repository = PortfolioOptimizerRepository()
        if gateway is None:
            from .quantdinger_gateway import QuantDingerOptimizerGateway

            gateway = QuantDingerOptimizerGateway()
        self.repository = repository
        self.gateway = gateway

    @staticmethod
    def _parse(payload: dict[str, Any]) -> tuple[dict[str, Any], tuple[Instrument, ...]]:
        if not isinstance(payload, dict):
            raise ValueError("invalid_optimizer_request")
        try:
            start = date.fromisoformat(str(payload.get("startDate") or ""))
            end = date.fromisoformat(str(payload.get("endDate") or ""))
        except ValueError as exc:
            raise ValueError("invalid_optimizer_date_range") from exc
        if end < start:
            raise ValueError("invalid_optimizer_date_range")
        if (end - start).days + 1 > 3_650:
            raise ValueError("optimizer_window_too_large")

        raw_instruments = payload.get("instruments")
        if not isinstance(raw_instruments, list) or not 1 <= len(raw_instruments) <= 10:
            raise ValueError("optimizer_instrument_limit")
        instruments = []
        seen = set()
        seen_symbols = set()
        for raw in raw_instruments:
            market = _MARKETS.get(str((raw or {}).get("market") or "").strip().lower())
            if market is None:
                raise ValueError("unsupported_optimizer_market")
            symbol = str((raw or {}).get("symbol") or "").strip().upper()
            currency = str((raw or {}).get("currency") or "").strip().upper()
            if not symbol or not currency or len(symbol) > 80 or len(currency) > 8:
                raise ValueError("invalid_optimizer_instrument")
            if market == "Forex":
                try:
                    symbol = canonicalize_supported_symbol(market, symbol)
                except ValueError as exc:
                    raise ValueError("unsupported_optimizer_market") from exc
                if currency != "USD":
                    raise ValueError("gold_currency_must_be_usd")
            key = (market, symbol)
            if key in seen:
                raise ValueError("duplicate_optimizer_instrument")
            if symbol in seen_symbols:
                raise ValueError("duplicate_optimizer_symbol")
            seen.add(key)
            seen_symbols.add(symbol)
            instruments.append(
                Instrument(
                    market=market,
                    symbol=symbol,
                    currency=currency,
                    exchange_id=str((raw or {}).get("exchangeId") or "").strip().lower(),
                    market_type=str((raw or {}).get("marketType") or "").strip().lower(),
                )
            )
        base_currency = str(payload.get("baseCurrency") or "USD").strip().upper()
        if not base_currency or len(base_currency) > 8:
            raise ValueError("invalid_base_currency")
        try:
            max_weight = float(payload.get("maxWeight", 1.0))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_max_weight") from exc
        normalized = {
            "method": str(payload.get("method") or "").strip(),
            "baseCurrency": base_currency,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "maxWeight": max_weight,
            "targetReturnPct": payload.get("targetReturnPct"),
            "targetVolatilityPct": payload.get("targetVolatilityPct"),
            "riskTolerance": payload.get("riskTolerance"),
            "instruments": [
                {
                    "market": item.market,
                    "symbol": item.symbol,
                    "currency": item.currency,
                    "exchangeId": item.exchange_id,
                    "marketType": item.market_type,
                }
                for item in instruments
            ],
        }
        return normalized, tuple(instruments)

    def create_run(self, *, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        request, instruments = self._parse(payload)
        original_series: list[PriceSeries] = []
        converted: dict[str, dict[int, float]] = {}
        fx_series: list[PriceSeries] = []
        fx_cache: dict[tuple[str, str], PriceSeries] = {}
        for instrument in instruments:
            series = self.gateway.fetch_daily(
                instrument, start_date=request["startDate"], end_date=request["endDate"]
            )
            _validate_series(series)
            original_series.append(series)
            values = dict(zip(series.timestamps, series.closes))
            if instrument.currency != request["baseCurrency"]:
                fx_key = (instrument.currency, request["baseCurrency"])
                fx = fx_cache.get(fx_key)
                if fx is None:
                    fx = self.gateway.fetch_fx(
                        instrument.currency,
                        request["baseCurrency"],
                        start_date=request["startDate"],
                        end_date=request["endDate"],
                    )
                if fx is None:
                    raise ValueError("production_fx_unavailable")
                _validate_series(fx)
                if fx_key not in fx_cache:
                    fx_cache[fx_key] = fx
                    fx_series.append(fx)
                rates = dict(zip(fx.timestamps, fx.closes))
                values = {timestamp: close * rates[timestamp] for timestamp, close in values.items() if timestamp in rates}
            converted[instrument.symbol] = values

        common = set.intersection(*(set(values) for values in converted.values()))
        timestamps = sorted(common)
        if len(timestamps) < 31:
            raise ValueError("insufficient_synchronized_prices")
        if len(timestamps) > 3_650:
            timestamps = timestamps[-3_650:]
        symbols = tuple(item.symbol for item in instruments)
        matrix = np.asarray([[converted[symbol][timestamp] for symbol in symbols] for timestamp in timestamps])
        result = optimize(
            OptimizerInput(
                symbols=symbols,
                prices=matrix,
                method=request["method"],
                max_weight=request["maxWeight"],
                target_return_pct=None if request["targetReturnPct"] is None else float(request["targetReturnPct"]),
                target_volatility_pct=None if request["targetVolatilityPct"] is None else float(request["targetVolatilityPct"]),
                risk_tolerance=None if request["riskTolerance"] is None else float(request["riskTolerance"]),
            )
        )
        snapshot = {
            "baseCurrency": request["baseCurrency"],
            "timestamps": timestamps,
            "convertedPrices": matrix.tolist(),
            "series": [_series_dict(item) for item in original_series],
            "fxSeries": [_series_dict(item) for item in fx_series],
        }
        input_checksum = _checksum(snapshot)
        run_id = self.repository.create_run(
            user_id=int(user_id),
            request=request,
            input_snapshot=snapshot,
            input_checksum=input_checksum,
            series=tuple(original_series + fx_series),
            result=result,
        )
        return {"id": run_id, "status": "SUCCEEDED", "inputChecksum": input_checksum, **result}

    def get_run(self, *, user_id: int, run_id: str):
        if not run_id or len(run_id) > 128:
            raise ValueError("invalid_optimizer_run_id")
        return self.repository.get_run(run_id=run_id, user_id=int(user_id))

    def preview(self, *, user_id: int, run_id: str, portfolio_value: float) -> dict[str, Any]:
        run = self.get_run(user_id=user_id, run_id=run_id)
        if run is None:
            raise LookupError("optimizer_run_not_found")
        try:
            value = float(portfolio_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_portfolio_value") from exc
        if not np.isfinite(value) or value <= 0:
            raise ValueError("invalid_portfolio_value")
        instrument_map = {item["symbol"]: item for item in run["request"]["instruments"]}
        snapshot = run["input_snapshot"]
        returns_only_symbols = sorted(
            str(item.get("symbol") or "")
            for item in (snapshot.get("series") or [])
            if item.get("markToMarketSupported") is False
        )
        if returns_only_symbols:
            raise ValueError(
                "optimizer_mark_to_market_unavailable: "
                + ",".join(returns_only_symbols)
            )
        snapshot_symbols = [item["symbol"] for item in run["request"]["instruments"]]
        converted_prices = snapshot.get("convertedPrices") or []
        if not converted_prices or len(converted_prices[-1]) != len(snapshot_symbols):
            raise ValueError("immutable_input_snapshot_unavailable")
        marks = {
            symbol: float(converted_prices[-1][index])
            for index, symbol in enumerate(snapshot_symbols)
        }
        current_positions = {
            (item["market"], item["symbol"]): float(item["quantity"])
            for item in self.repository.list_managed_positions(user_id=int(user_id))
        }
        orders = []
        for allocation in run["result"]["allocations"]:
            symbol = allocation["symbol"]
            mark = marks.get(symbol, 0.0)
            if not np.isfinite(mark) or mark <= 0:
                raise ValueError("mark_price_unavailable")
            notional = value * int(allocation["weightBps"]) / 10_000
            instrument = instrument_map[symbol]
            target_quantity = round(notional / mark, 8)
            current_quantity = current_positions.get((instrument["market"], symbol), 0.0)
            delta = round(target_quantity - current_quantity, 8)
            orders.append(
                {
                    "market": instrument["market"],
                    "symbol": symbol,
                    "side": "BUY" if delta >= 0 else "SELL",
                    "targetWeightBps": int(allocation["weightBps"]),
                    "currentQuantity": current_quantity,
                    "targetQuantity": target_quantity,
                    "quantity": abs(delta),
                    "markPrice": mark,
                    "notional": round(abs(delta) * mark, 8),
                    "currency": run["request"]["baseCurrency"],
                    "executionMode": "SIMULATED",
                }
            )
        plan = self.repository.create_plan(
            run_id=run_id,
            user_id=int(user_id),
            portfolio_value=value,
            input_checksum=run["input_checksum"],
            orders=orders,
        )
        return {**plan, "executionMode": "SIMULATED", "orders": orders}

    def apply(self, *, user_id: int, run_id: str, plan_id: str, idempotency_key: str):
        if self.get_run(user_id=user_id, run_id=run_id) is None:
            raise LookupError("optimizer_run_not_found")
        key = str(idempotency_key or "").strip()
        if not 8 <= len(key) <= 128:
            raise ValueError("invalid_idempotency_key")
        result = self.repository.apply_plan(
            plan_id=plan_id,
            run_id=run_id,
            user_id=int(user_id),
            idempotency_key=key,
        )
        if result is None:
            raise LookupError("rebalance_plan_not_found")
        if result.get("executionMode") != "SIMULATED":
            raise RuntimeError("paper_execution_boundary_violated")
        return result


@lru_cache(maxsize=1)
def get_portfolio_optimizer_service() -> PortfolioOptimizerService:
    return PortfolioOptimizerService()


__all__ = ["PortfolioOptimizerService", "get_portfolio_optimizer_service"]
