"""The post-deploy canary must detect broken public contracts without hiding provider gaps."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "deploy" / "vps" / "check_public_contract.py"


def _module():
    spec = importlib.util.spec_from_file_location("check_public_contract", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_live_assets_canary_accepts_explicit_hose_provider_gap():
    module = _module()
    warnings = module.validate_live_assets({
        "code": 1,
        "data": {"fetchedAt": "2026-10-03T00:00:00Z", "assets": [
            {"market": "VNStock", "symbol": "VNINDEX", "status": "UNAVAILABLE", "price": 0},
            {"market": "VNStock", "symbol": "VN30", "status": "UNAVAILABLE", "price": 0},
        ]},
    })
    assert len(warnings) == 2


def test_live_assets_canary_rejects_missing_provenance_for_a_price():
    module = _module()
    with pytest.raises(ValueError, match="source"):
        module.validate_live_assets({
            "code": 1,
            "data": {"fetchedAt": "2026-10-03T00:00:00Z", "assets": [
                {"market": "VNStock", "symbol": symbol, "status": "DAILY", "price": 1500,
                 "observedAt": "2026-10-02T00:00:00Z"}
                for symbol in ("VNINDEX", "VN30")
            ]},
        })


def test_overview_canary_requires_archive_label_for_stale_snapshot():
    module = _module()
    with pytest.raises(ValueError, match="archive"):
        module.validate_overview({
            "code": 1,
            "data": {"asOf": "2026-09-01", "snapshotFreshness": "STALE", "mode": "live"},
        })
