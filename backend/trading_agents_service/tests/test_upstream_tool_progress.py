from __future__ import annotations

import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.upstream_config import NativeToolObserver


def test_native_tool_observer_reports_safe_live_tool_progress() -> None:
    progress: list[dict[str, str]] = []
    observer = NativeToolObserver(
        {"data_vendors": {"core_stock_apis": "yfinance"}, "tool_vendors": {}},
        on_progress=progress.append,
    )

    observer.on_tool_start({"name": "get_stock_data"}, "private input is never forwarded", run_id="tool-run")

    assert progress == [{
        "event_type": "tool_started",
        "tool_name": "get_stock_data",
        "category": "core_stock_apis",
        "vendor_chain": "yfinance",
    }]
