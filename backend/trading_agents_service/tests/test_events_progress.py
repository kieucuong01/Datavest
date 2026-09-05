from __future__ import annotations

import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.events import event_from_chunk


def test_native_chunk_progress_event_contains_stage_without_report_payload() -> None:
    event = event_from_chunk(
        "run-123",
        1,
        {"market_report": "private report body", "data": {"secret": "not for browser"}},
    )

    assert event.payload == {"stage_id": "market"}
