from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


def _evidence(**overrides):
    payload = {
        "version": "vietnam-evidence-v1",
        "asOf": "2026-09-16T16:59:59.999999+00:00",
        "instrument": {
            "market": "VNStock",
            "exchange": "HOSE",
            "symbol": "FPT",
            "name": "FPT Corporation",
            "sector": "Technology",
        },
        "price": {"price": 123.0, "volume": 100000, "priceMode": "adjusted"},
        "technical": {"rsi": {"value": 55.0}, "trend": "uptrend"},
        "fundamentals": {
            "observations": [{
                "metric": "revenue",
                "value": 1000,
                "periodEnd": "2026-06-30",
                "availableAt": "2026-08-01T00:00:00+00:00",
                "source": "vndirect",
            }],
            "derivedMetrics": {"pe_ratio": 20.5, "return_on_equity": 18.2},
        },
        "corporateActions": [],
        "disclosures": [{
            "title": "Quarterly results",
            "availableAt": "2026-08-01T00:00:00+00:00",
            "source": "vndirect",
        }],
        "marketContext": {"benchmarks": {"VNINDEX": {"price": 1500}}},
        "dataGaps": [{"field": "foreignRoom", "reason": "NO_VERIFIED_FREE_SOURCE"}],
        "sources": [{"provider": "vndirect", "url": "https://dstock.vndirect.com.vn"}],
    }
    payload.update(overrides)
    checksum = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**payload, "checksum": checksum}


def test_validates_and_formats_bounded_authoritative_hose_context():
    from app.vietnam_evidence import (
        evidence_provenance,
        format_vietnam_evidence_context,
        validate_vietnam_evidence,
    )

    evidence = validate_vietnam_evidence(
        _evidence(), ticker="FPT.VN", analysis_date="2026-09-16"
    )
    context = format_vietnam_evidence_context(evidence)

    assert "DATAVEST_VIETNAM_EVIDENCE" in context
    assert "authoritative point-in-time" in context
    assert '"price":123.0' in context
    assert "NO_VERIFIED_FREE_SOURCE" in context
    assert len(context) <= 12_000
    assert evidence_provenance(evidence) == {
        "version": "vietnam-evidence-v1",
        "checksum": evidence["checksum"],
        "asOf": "2026-09-16T16:59:59.999999+00:00",
        "providers": ["vndirect"],
        "gapCount": 1,
    }


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda item: {**item, "checksum": "0" * 64}, "checksum"),
        (lambda item: _evidence(instrument={**item["instrument"], "symbol": "VCB"}), "symbol"),
        (lambda item: _evidence(asOf="2026-09-17T00:00:00+00:00"), "cutoff"),
    ],
)
def test_rejects_tampered_mismatched_or_future_evidence(mutate, message):
    from app.vietnam_evidence import VietnamEvidenceValidationError, validate_vietnam_evidence

    with pytest.raises(VietnamEvidenceValidationError, match=message):
        validate_vietnam_evidence(
            mutate(_evidence()), ticker="FPT.VN", analysis_date="2026-09-16"
        )


def test_rejects_oversized_evidence_even_with_valid_checksum():
    from app.vietnam_evidence import VietnamEvidenceValidationError, validate_vietnam_evidence

    evidence = _evidence(technical={"blob": "x" * (512 * 1024)})

    with pytest.raises(VietnamEvidenceValidationError, match="too large"):
        validate_vietnam_evidence(evidence, ticker="FPT.VN", analysis_date="2026-09-16")


def test_rejects_malformed_fundamental_section_with_contract_error():
    from app.vietnam_evidence import VietnamEvidenceValidationError, validate_vietnam_evidence

    with pytest.raises(VietnamEvidenceValidationError, match="fundamentals"):
        validate_vietnam_evidence(
            _evidence(fundamentals=["invalid"]), ticker="FPT.VN", analysis_date="2026-09-16"
        )


def test_rejects_fundamental_period_after_analysis_cutoff():
    from app.vietnam_evidence import VietnamEvidenceValidationError, validate_vietnam_evidence

    evidence = _evidence(fundamentals={
        "observations": [{
            "metric": "revenue",
            "value": 1000,
            "periodEnd": "2026-09-30",
            "availableAt": "2026-09-10T00:00:00+00:00",
            "source": "vndirect",
        }],
        "derivedMetrics": {},
    })

    with pytest.raises(VietnamEvidenceValidationError, match="period"):
        validate_vietnam_evidence(evidence, ticker="FPT.VN", analysis_date="2026-09-16")


def test_rejects_future_market_context_timestamp():
    from app.vietnam_evidence import VietnamEvidenceValidationError, validate_vietnam_evidence

    evidence = _evidence(marketContext={
        "benchmarks": {
            "VNINDEX": {
                "price": 1500,
                "observedAt": "2026-09-17T00:00:00+00:00",
            }
        }
    })

    with pytest.raises(VietnamEvidenceValidationError, match="cutoff"):
        validate_vietnam_evidence(evidence, ticker="FPT.VN", analysis_date="2026-09-16")


def test_allows_later_fetch_time_and_announced_future_event_date():
    from app.vietnam_evidence import validate_vietnam_evidence

    evidence = _evidence(
        provenance={"price": {"fetchedAt": "2026-10-03T00:00:00+00:00"}},
        corporateActions=[{
            "availableAt": "2026-09-10T00:00:00+00:00",
            "effectiveDate": "2026-10-15",
            "title": "Dividend announced before analysis date",
        }],
    )

    assert validate_vietnam_evidence(
        evidence, ticker="FPT.VN", analysis_date="2026-09-16"
    )["checksum"] == evidence["checksum"]


def test_rejects_fundamental_revision_after_analysis_cutoff():
    from app.vietnam_evidence import VietnamEvidenceValidationError, validate_vietnam_evidence

    evidence = _evidence(fundamentals={
        "observations": [{
            "metric": "revenue", "value": 1000, "periodEnd": "2025-12-31",
            "availableAt": "2026-03-30T00:00:00+00:00",
            "revisionAt": "2026-10-01T00:00:00+00:00",
        }],
    })

    with pytest.raises(VietnamEvidenceValidationError, match="revisionAt"):
        validate_vietnam_evidence(evidence, ticker="FPT.VN", analysis_date="2026-09-16")
