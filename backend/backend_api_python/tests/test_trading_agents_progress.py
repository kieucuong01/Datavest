"""Progress and public-event contracts for TradingAgents runs."""

from __future__ import annotations

import sys
import types
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _enable_lightweight_app_imports() -> None:
    if "app" not in sys.modules:
        package = types.ModuleType("app")
        package.__path__ = [str(BACKEND_ROOT / "app")]
        sys.modules["app"] = package
    if "app.utils" not in sys.modules:
        package = types.ModuleType("app.utils")
        package.__path__ = [str(BACKEND_ROOT / "app" / "utils")]
        sys.modules["app.utils"] = package


def test_progress_uses_observed_stage_events_and_names_next_stage() -> None:
    _enable_lightweight_app_imports()
    from app.services.trading_agents_progress import build_public_progress

    result = build_public_progress(
        status="running",
        market="VNStock",
        events=[
            {"event_type": "upstream_chunk", "payload_json": {"stage_id": "market"}},
            {"event_type": "upstream_chunk", "payload_json": {"stage_id": "social"}},
        ],
        artifacts=[],
    )

    assert result["completed_stage_ids"] == ["market", "social"]
    assert result["current_stage_id"] == "news"
    assert 5 < result["percent"] < 50
    assert result["completed_count"] == 2
    assert result["total_count"] == 10


def test_succeeded_run_reaches_one_hundred_only_with_report_artifact() -> None:
    _enable_lightweight_app_imports()
    from app.services.trading_agents_progress import build_public_progress

    without_artifact = build_public_progress(
        status="succeeded",
        market="Crypto",
        events=[],
        artifacts=[],
    )
    with_artifact = build_public_progress(
        status="succeeded",
        market="Crypto",
        events=[],
        artifacts=[{"artifact_name": "complete_report.md"}],
    )

    assert without_artifact["percent"] < 100
    assert with_artifact["percent"] == 100
    assert with_artifact["current_stage_id"] == "report"


def test_public_event_does_not_expose_raw_upstream_payload() -> None:
    _enable_lightweight_app_imports()
    from app.services.trading_agents_progress import public_event

    event = public_event(
        {
            "sequence": 4,
            "event_type": "upstream_chunk",
            "created_at": "2026-09-05T00:00:00+00:00",
            "payload_json": {
                "stage_id": "market",
                "market_report": "private model output must stay server-side",
            },
        }
    )

    assert event == {
        "sequence": 4,
        "event_type": "upstream_chunk",
        "created_at": "2026-09-05T00:00:00+00:00",
        "payload": {"stage_id": "market"},
    }
