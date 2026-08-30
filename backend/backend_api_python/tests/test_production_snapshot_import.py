from __future__ import annotations


def _metric(**overrides):
    row = {
        "asset": "BTC",
        "effectiveStart": "2026-08-24T19:38:00.885Z",
        "effectiveEnd": "2026-08-24T19:38:00.885Z",
        "market": "crypto",
        "methodologyVersion": "crypto-regime-v1",
        "metricCode": "crypto.network.difficulty",
        "observedAt": "2026-08-24T19:38:00.885Z",
        "qualityWarnings": [],
        "sourceCode": "mempool-space",
        "sourceUrl": "https://mempool.space/api/v1/difficulty-adjustment",
        "unit": "index",
        "value": "123.45",
    }
    row.update(overrides)
    return row


def test_production_metric_maps_to_live_observation_with_provenance():
    from app.tools.import_production_smart_insights_snapshot import production_metric_observation

    observation = production_metric_observation(_metric())

    assert observation.source_code == "mempool-space"
    assert observation.data_class.value == "LIVE"
    assert observation.symbol == "BTC"
    assert observation.value["metric"] == "crypto.network.difficulty"
    assert observation.value["value"] == "123.45"
    assert len(observation.checksum) == 64


def test_production_deribit_alias_maps_to_local_openbb_source():
    from app.tools.import_production_smart_insights_snapshot import production_metric_observation

    observation = production_metric_observation(
        _metric(
            sourceCode="deribit-public",
            sourceUrl="https://www.deribit.com/api/v2/public/get_index_price",
        )
    )

    assert observation.source_code == "openbb-deribit"


def test_rejects_unknown_or_insecure_production_metric_source():
    import pytest

    from app.tools.import_production_smart_insights_snapshot import SnapshotImportError, production_metric_observation

    with pytest.raises(SnapshotImportError, match="unknown_source"):
        production_metric_observation(_metric(sourceCode="untrusted-source"))
    with pytest.raises(SnapshotImportError, match="invalid_observation"):
        production_metric_observation(_metric(sourceUrl="http://example.test/raw"))


def test_calendar_event_maps_to_macro_observation():
    from app.tools.import_production_smart_insights_snapshot import production_calendar_observation

    observation = production_calendar_observation(
        {
            "event": "US CPI",
            "eventAt": "2026-08-25T12:30:00.000Z",
            "impact": "high",
            "observedAt": "2026-08-24T22:00:00.000Z",
            "sourceCode": "cryptocraft",
            "sourceUrl": "https://www.cryptocraft.com/calendar?week=this",
        }
    )

    assert observation.market == "macro"
    assert observation.value["metric"] == "macro.economic_event"
    assert observation.value["event"] == "US CPI"


def test_calendar_date_without_time_is_normalized_to_utc_midnight():
    from app.tools.import_production_smart_insights_snapshot import production_calendar_observation

    observation = production_calendar_observation(
        {
            "event": "Holiday",
            "eventDate": "2026-08-26",
            "observedAt": "2026-08-24T22:00:00.000Z",
            "sourceCode": "cryptocraft",
            "sourceUrl": "https://www.cryptocraft.com/calendar?week=this",
        }
    )

    assert observation.effective_at.isoformat() == "2026-08-26T00:00:00+00:00"
