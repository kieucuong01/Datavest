from __future__ import annotations

import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.events import RunEvent
from app.progress import StageProgressTracker


def test_stage_tracker_announces_current_stage_and_heartbeat_without_fake_completion() -> None:
    published: list[tuple[str, dict[str, object]]] = []
    tracker = StageProgressTracker(
        asset_type="crypto",
        publish=lambda event_type, payload: published.append((event_type, dict(payload))),
    )

    tracker.start()
    tracker.heartbeat()

    assert published[0] == (
        "stage_started",
        {
            "stage_id": "market",
            "completed_count": 0,
            "total_count": 9,
            "percent": 5,
            "stage_number": 1,
        },
    )
    assert published[1][0] == "stage_heartbeat"
    assert published[1][1]["stage_id"] == "market"
    assert published[1][1]["completed_count"] == 0
    assert published[1][1]["percent"] == 5


def test_stage_tracker_moves_forward_only_after_a_native_graph_chunk() -> None:
    published: list[tuple[str, dict[str, object]]] = []
    tracker = StageProgressTracker(
        asset_type="crypto",
        publish=lambda event_type, payload: published.append((event_type, dict(payload))),
    )

    tracker.start()
    tracker.on_graph_event(RunEvent("run-1", 1, "upstream_chunk", {"stage_id": "market"}))

    assert published[-1] == (
        "stage_started",
        {
            "stage_id": "social",
            "completed_count": 1,
            "total_count": 9,
            "percent": 16,
            "stage_number": 2,
        },
    )
