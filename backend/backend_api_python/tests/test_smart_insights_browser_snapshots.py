from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest


NOW = datetime(2026, 8, 30, 2, 0, tzinfo=timezone.utc)


def _fear_greed_payload(*, fetched_at: datetime = NOW) -> dict[str, object]:
    return {
        "source": "alternative-fng",
        "source_url": "https://alternative.me/crypto/fear-and-greed-index/",
        "schema_version": 1,
        "fetched_at": fetched_at.isoformat(),
        "coverage": {
            "record_count": 1,
            "oldest_effective_at": "2026-08-29T00:00:00+00:00",
            "newest_effective_at": "2026-08-29T00:00:00+00:00",
        },
        "records": [
            {
                "effective_at": "2026-08-29T00:00:00+00:00",
                "metric": "crypto.fear_greed.index",
                "value": "67",
                "unit": "index",
                "classification": "Greed",
            }
        ],
    }


def test_write_snapshot_keeps_prior_valid_file_when_new_payload_is_invalid(tmp_path):
    from app.services.smart_insights.browser_snapshots import (
        SnapshotUnavailable,
        load_snapshot,
        write_snapshot,
    )

    write_snapshot("alternative-fng", _fear_greed_payload(), root=tmp_path)
    with pytest.raises(SnapshotUnavailable, match="REQUIRED_RECORDS"):
        write_snapshot("alternative-fng", {**_fear_greed_payload(), "records": []}, root=tmp_path)

    assert load_snapshot("alternative-fng", root=tmp_path, now=NOW)["records"][0]["value"] == "67"


def test_load_snapshot_rejects_source_mismatch_and_stale_payload(tmp_path):
    from app.services.smart_insights.browser_snapshots import (
        SnapshotUnavailable,
        load_snapshot,
    )

    target = tmp_path / "alternative-fng.json"
    target.write_text(json.dumps({**_fear_greed_payload(), "source": "cbbi-public"}), encoding="utf-8")
    with pytest.raises(SnapshotUnavailable, match="SOURCE_IDENTITY_MISMATCH"):
        load_snapshot("alternative-fng", root=tmp_path, now=NOW)

    target.write_text(
        json.dumps(_fear_greed_payload(fetched_at=NOW - timedelta(days=3))), encoding="utf-8"
    )
    with pytest.raises(SnapshotUnavailable, match="STALE_SNAPSHOT"):
        load_snapshot("alternative-fng", root=tmp_path, now=NOW)
