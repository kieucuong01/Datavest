"""Bounded JSON bridge for the optional OpenBB Deribit provider."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import sys
from typing import Any

from openbb_deribit.models.futures_curve import DeribitFuturesCurveFetcher
from openbb_deribit.models.futures_historical import DeribitFuturesHistoricalFetcher
from openbb_deribit.models.options_chains import DeribitOptionsChainsFetcher


ASSETS = ("BTC", "ETH")


def _parse_as_of(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--as-of must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _dump_row(row: Any) -> dict[str, Any]:
    value = row.model_dump(mode="json") if hasattr(row, "model_dump") else row
    if not isinstance(value, dict):
        raise ValueError("OpenBB returned an invalid row")
    return value


def _options_snapshot(row: Any) -> dict[str, Any]:
    value = _dump_row(row)
    fields = (
        "underlying_symbol",
        "underlying_price",
        "contract_symbol",
        "expiration",
        "dte",
        "strike",
        "option_type",
        "contract_size",
        "open_interest",
        "volume",
        "implied_volatility",
        "delta",
        "underlying_spot_price",
        "timestamp",
    )
    return {field: value.get(field) for field in fields}


async def _collect(as_of: datetime) -> dict[str, object]:
    start_date = (as_of - timedelta(days=3)).date().isoformat()
    end_date = as_of.date().isoformat()
    futures_curve: dict[str, list[dict[str, Any]]] = {}
    futures_historical: dict[str, list[dict[str, Any]]] = {}
    options_chains: dict[str, list[dict[str, Any]]] = {}
    for asset in ASSETS:
        curve, historical, options = await asyncio.gather(
            DeribitFuturesCurveFetcher.fetch_data({"symbol": asset}),
            DeribitFuturesHistoricalFetcher.fetch_data(
                {
                    "symbol": asset,
                    "start_date": start_date,
                    "end_date": end_date,
                    "interval": "1d",
                }
            ),
            DeribitOptionsChainsFetcher.fetch_data({"symbol": asset}),
        )
        if not isinstance(curve, list) or not isinstance(historical, list):
            raise ValueError("OpenBB returned an invalid futures response")
        option_rows = options.model_dump(mode="json") if hasattr(options, "model_dump") else options
        if not isinstance(option_rows, list):
            raise ValueError("OpenBB returned an invalid options response")
        futures_curve[asset] = [_dump_row(row) for row in curve]
        futures_historical[asset] = [_dump_row(row) for row in historical]
        options_chains[asset] = [_options_snapshot(row) for row in option_rows]
    return {
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "futures_curve": futures_curve,
        "futures_historical": futures_historical,
        "options_chains": options_chains,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    try:
        payload = asyncio.run(_collect(_parse_as_of(args.as_of)))
    except Exception as error:
        print(f"OPENBB_DERIBIT_ERROR: {type(error).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
