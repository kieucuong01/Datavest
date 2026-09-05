from __future__ import annotations

import hashlib
import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.upstream_config import NativeToolObserver, extract_native_environment, upstream_tool_groups


def test_all_native_tool_groups_are_reported() -> None:
    assert upstream_tool_groups() == {
        "market",
        "social",
        "news",
        "fundamentals",
        "core_stock_apis",
        "technical_indicators",
        "fundamental_data",
        "news_data",
        "macro_data",
        "prediction_markets",
    }


def test_preserves_native_tradingagents_environment_without_unrelated_values() -> None:
    environment = {
        "TRADINGAGENTS_LLM_PROVIDER": "deepseek",
        "TRADINGAGENTS_OUTPUT_LANGUAGE": "Vietnamese",
        "DEEPSEEK_API_KEY": "not-a-real-key",
        "UNRELATED_VALUE": "must-not-pass",
    }

    assert extract_native_environment(environment) == {
        "TRADINGAGENTS_LLM_PROVIDER": "deepseek",
        "TRADINGAGENTS_OUTPUT_LANGUAGE": "Vietnamese",
        "DEEPSEEK_API_KEY": "not-a-real-key",
    }


def test_native_tool_observer_records_vendor_status_duration_and_checksum() -> None:
    observer = NativeToolObserver(
        {
            "data_vendors": {"core_stock_apis": "yfinance,alpha_vantage"},
            "tool_vendors": {},
        }
    )

    observer.on_tool_start({"name": "get_stock_data"}, "{}", run_id="tool-run")
    observer.on_tool_end("OHLCV", run_id="tool-run")
    observer.on_tool_start({"name": "get_stock_data"}, "{}", run_id="no-data")
    observer.on_tool_end("NO_DATA_AVAILABLE: missing", run_id="no-data")
    observer.on_tool_start({"name": "get_stock_data"}, "{}", run_id="failed")
    observer.on_tool_error(RuntimeError("provider unavailable"), run_id="failed")

    configured, unavailable, failed = observer.events()

    assert configured.vendor_chain == "yfinance,alpha_vantage"
    assert configured.status == "configured"
    assert configured.duration_ms >= 0
    assert configured.result_checksum == hashlib.sha256(b"OHLCV").hexdigest()
    assert unavailable.status == "unavailable"
    assert unavailable.result_checksum
    assert failed.status == "error"
    assert failed.result_checksum
