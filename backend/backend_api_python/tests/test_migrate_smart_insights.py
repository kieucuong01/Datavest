from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest


def _raw(*, status: str = "validated") -> dict:
    return {
        "id": "raw-1",
        "source_url": "https://fred.stlouisfed.org/graph/fredgraph.csv",
        "status": status,
        "observed_at": datetime(2026, 8, 17, 2, tzinfo=timezone.utc),
    }


def _metric(*, quality_status: str = "passed") -> dict:
    return {
        "id": "metric-1",
        "raw_snapshot_id": "raw-1",
        "provider_code": "fred",
        "source_url": "https://fred.stlouisfed.org/graph/fredgraph.csv",
        "effective_at": datetime(2026, 8, 16, tzinfo=timezone.utc),
        "observed_at": datetime(2026, 8, 17, 2, tzinfo=timezone.utc),
        "published_at": None,
        "metric_code": "macro.yield.10y_pct",
        "market": "macro",
        "unit": "%",
        "methodology_version": "fred-v1",
        "dimensions": {"providerSeries": "DGS10"},
        "quality_status": quality_status,
        "quality_flags": [],
        "value": Decimal("4.21"),
        "natural_key": "fred:DGS10:2026-08-16",
        "revision": 1,
        "asset_symbol": None,
    }


def test_legacy_live_classification_requires_validated_raw_and_successful_run():
    from app.tools.migrate_smart_insights import _quality_class
    from app.services.smart_insights.contracts import DataClass

    assert _quality_class("validated", "succeeded", "passed") == DataClass.LIVE
    assert _quality_class("fetched", "succeeded", "passed") is None
    assert _quality_class("validated", "failed", "passed") is None
    assert _quality_class("fetched", "failed", "sample") == DataClass.DEMO


def test_legacy_metric_maps_to_the_new_observation_contract():
    from app.tools.migrate_smart_insights import _metric_observation

    row = _metric()
    observation = _metric_observation(row, _raw(), {"status": "succeeded"})

    assert observation is not None
    assert observation.source_code == "fred"
    assert observation.data_class.value == "LIVE"
    assert observation.value["metric"] == "macro.yield.10y_pct"
    assert observation.value["value"] == "4.21"
    assert observation.value["legacyObservationId"] == "metric-1"
    assert len(observation.checksum) == 64


def test_invalid_provider_url_is_rejected_without_fabricating_evidence():
    from app.tools.migrate_smart_insights import _metric_observation

    row = _metric()
    row["source_url"] = "http://internal.example/secret"
    assert _metric_observation(row, _raw(), {"status": "succeeded"}) is None


def test_apply_refuses_same_source_and_destination_database():
    from app.tools.migrate_smart_insights import migrate

    with pytest.raises(ValueError, match="must differ"):
        migrate(
            source_dsn="postgresql://source:secret@127.0.0.1:5432/datavest",
            target_dsn="postgresql://target:other@127.0.0.1:5432/datavest",
            apply=True,
        )
