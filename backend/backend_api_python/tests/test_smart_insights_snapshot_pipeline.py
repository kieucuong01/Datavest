"""Immutable snapshot/opinion materialization contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


AS_OF = datetime(2026, 8, 24, 3, 0, tzinfo=timezone.utc)


def _evidence(identifier: str, *, metric: str, symbol: str | None = "BTC", data_class="LIVE"):
    return {
        "id": identifier,
        "market": "crypto",
        "symbol": symbol,
        "dataClass": data_class,
        "source": "openbb-deribit",
        "sourceUrl": "https://docs.openbb.co/odp/python/extensions/providers",
        "observedAt": "2026-08-24T02:00:00+00:00",
        "effectiveAt": "2026-08-23T00:00:00+00:00",
        "methodologyVersion": "openbb-deribit-v1",
        "checksum": (identifier[-1] * 64),
        "warnings": [],
        "value": {"metric": metric, "value": "0.8", "evidenceOnly": True},
    }


def test_live_snapshot_is_order_stable_and_links_asset_evidence():
    from app.services.smart_insights.snapshot_pipeline import build_snapshot_draft

    evidence = [
        _evidence("obs-a", metric="crypto.derivatives.options.put_call_open_interest_ratio"),
        _evidence("obs-b", metric="crypto.derivatives.futures.near_term_annualized_basis"),
    ]
    first = build_snapshot_draft(evidence, market="crypto", mode="live", as_of=AS_OF)
    second = build_snapshot_draft(list(reversed(evidence)), market="crypto", mode="live", as_of=AS_OF)

    assert first.evidence_checksum == second.evidence_checksum
    assert first.status == "COMPLETE"
    assert first.data_class == "LIVE"
    assert first.summary["metricCount"] == 2
    assert len(first.opinions) == 1
    opinion = first.opinions[0]
    assert opinion.symbol == "BTC"
    assert opinion.stance == "NEUTRAL"
    assert opinion.explanation is None
    assert opinion.evidence_validated is True
    assert set(opinion.evidence_ids) == {"obs-a", "obs-b"}


def test_snapshot_deduplicates_repeated_evidence_ids_before_linking():
    from app.services.smart_insights.snapshot_pipeline import build_snapshot_draft

    draft = build_snapshot_draft(
        [
            _evidence("obs-a", metric="crypto.derivatives.perpetual.funding_annualized"),
            _evidence("obs-a", metric="crypto.derivatives.perpetual.open_interest_usd"),
        ],
        market="crypto",
        mode="live",
        as_of=AS_OF,
    )

    assert draft.opinions[0].evidence_ids == ("obs-a",)
    assert draft.evidence_ids == ("obs-a",)


def test_live_snapshot_rejects_demo_before_persistence():
    from app.services.smart_insights.contracts import EvidencePolicyError
    from app.services.smart_insights.snapshot_pipeline import build_snapshot_draft

    with pytest.raises(EvidencePolicyError, match="DEMO_EVIDENCE_FORBIDDEN"):
        build_snapshot_draft(
            [_evidence("obs-d", metric="crypto.demo", data_class="DEMO")],
            market="crypto",
            mode="live",
            as_of=AS_OF,
        )


def test_materializer_groups_markets_and_publishes_immutable_drafts():
    from app.services.smart_insights.snapshot_pipeline import SnapshotMaterializer

    class Repository:
        def __init__(self):
            self.drafts = []

        def load_snapshot_evidence(self, run_id):
            assert run_id == "run-1"
            macro = {**_evidence("obs-c", metric="macro.yield.10y_pct", symbol=None), "market": "macro"}
            return [
                _evidence("obs-a", metric="crypto.derivatives.options.put_call_open_interest_ratio"),
                _evidence("obs-b", metric="crypto.derivatives.futures.near_term_annualized_basis"),
                macro,
            ]

        def publish_snapshot(self, draft):
            self.drafts.append(draft)
            return f"snapshot-{draft.market}", True

    repository = Repository()
    result = SnapshotMaterializer(repository=repository, clock=lambda: AS_OF).publish_for_run("run-1")

    assert result == [
        {"snapshotId": "snapshot-crypto", "market": "crypto", "created": True},
        {"snapshotId": "snapshot-macro", "market": "macro", "created": True},
    ]
    assert [draft.market for draft in repository.drafts] == ["crypto", "macro"]
    assert repository.drafts[1].opinions == ()
