#!/usr/bin/env python3
"""Post-deploy public API canary; free-provider outages are visible warnings."""

from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.request import Request, urlopen


def _data(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("code") != 1:
        raise ValueError("public API did not return a successful envelope")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("public API data is missing")
    return data


def validate_live_assets(payload: object) -> list[str]:
    data = _data(payload)
    if not data.get("fetchedAt") or not isinstance(data.get("assets"), list):
        raise ValueError("live-assets timestamp or assets are missing")
    rows = {
        row.get("symbol"): row
        for row in data["assets"]
        if isinstance(row, dict) and row.get("market") == "VNStock"
    }
    warnings = []
    for symbol in ("VNINDEX", "VN30"):
        row = rows.get(symbol)
        if not row:
            raise ValueError(f"HOSE canary asset {symbol} is missing")
        status = row.get("status")
        if status not in {"DAILY", "DELAYED", "LIVE", "STALE", "UNAVAILABLE"}:
            raise ValueError(f"HOSE canary asset {symbol} has invalid status")
        if status == "UNAVAILABLE":
            warnings.append(f"{symbol} provider is unavailable")
            continue
        if not row.get("source") or not row.get("observedAt"):
            raise ValueError(f"HOSE canary asset {symbol} has price without source/observedAt")
        if not isinstance(row.get("price"), (int, float)) or row["price"] <= 0:
            raise ValueError(f"HOSE canary asset {symbol} has invalid price")
        if status == "STALE":
            warnings.append(f"{symbol} provider price is stale")
    return warnings


def validate_overview(payload: object) -> list[str]:
    data = _data(payload)
    freshness = data.get("snapshotFreshness")
    if freshness not in {"FRESH", "STALE", "UNAVAILABLE"}:
        raise ValueError("public overview snapshot freshness is missing")
    if freshness == "STALE":
        if data.get("mode") != "archive" or not data.get("asOf"):
            raise ValueError("stale public overview must be labelled archive with asOf")
        return [f"public opinion snapshot is archived as of {data['asOf']}"]
    return []


def _fetch(url: str) -> object:
    last_error = None
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=25) as response:
                return json.load(response)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(3)
    raise RuntimeError(f"public canary request failed: {url}: {last_error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://datavest.vn")
    args = parser.parse_args(argv)
    base_url = args.base_url.rstrip("/")
    try:
        warnings = validate_live_assets(_fetch(f"{base_url}/api/smart-insights/public/live-assets"))
        warnings += validate_overview(_fetch(f"{base_url}/api/smart-insights/public/overview"))
    except (ValueError, RuntimeError) as exc:
        print(f"Public canary failed: {exc}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"::warning::{warning}")
    print("Public Smart Insights API contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
