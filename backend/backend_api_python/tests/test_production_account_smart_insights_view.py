"""Contracts for rendering a tenant's imported legacy Smart Insights briefing."""

from app.services.smart_insights.production_account_view import (
    build_imported_crypto_market_pulse,
    build_imported_overview,
    merge_imported_crypto_market_pulse,
)


def _briefing():
    return {
        "id": "briefing-prod-1",
        "localDate": "2026-08-25",
        "status": "quant_only",
        "overallDataConfidence": 0.82,
        "primary": {"title": "Quant brief", "thesis": "Portfolio remains diversified"},
        "riskAlerts": [{"symbol": "HPG", "severity": "medium", "message": "Watch liquidity"}],
        "portfolioState": {"dataAsOf": "2026-08-25", "currency": "USD"},
        "assetOpinions": [
            {
                "symbol": "BTC",
                "assetName": "Bitcoin",
                "stance": "Tích cực",
                "quantScore": 64.25,
                "confidence": 0.8,
                "portfolioWeightPct": 54.11,
                "thesis": "Production-backed thesis",
                "supportingEvidenceIds": ["legacy-evidence-1"],
            },
            {
                "symbol": "HPG",
                "assetName": "Hoa Phat Group",
                "stance": "Thận trọng",
                "quantScore": -18.21,
                "confidence": 0.67,
                "portfolioWeightPct": 12.75,
                "thesis": "Vietnam equity thesis",
            },
            {
                "symbol": "XAU",
                "assetName": "Gold",
                "stance": "Tăng",
                "quantScore": 26.49,
                "confidence": 0.55,
                "portfolioWeightPct": 33.14,
                "thesis": "Gold thesis",
            },
        ],
        "portfolioChanges": [
            {
                "symbol": "XAU",
                "assetName": "Gold",
                "changeType": "reduce",
                "reason": "Quant change",
                "scoreDelta": -0.9,
            }
        ],
    }


def _pulse():
    return {
        "generatedAt": "2026-08-25T01:00:00Z",
        "fearGreed": {
            "status": "system",
            "sourceCode": "alternative-me",
            "sourceUrl": "https://alternative.me/crypto/fear-and-greed-index/",
            "latest": {"value": 66, "effectiveAt": "2026-08-25"},
            "series": [{"value": 64, "effectiveAt": "2026-08-24"}],
        },
        "etfFlows": {
            "status": "AVAILABLE",
            "sourceCodes": ["farside-btc-etf"],
            "summaries": [{"asset": "BTC", "latest": 501500000, "effectiveAt": "2026-08-25"}],
            "series": [],
        },
        "cycleIndicators": {"status": "AVAILABLE", "value": 57},
        "largeAddressActivity": {"status": "AVAILABLE", "value": 3},
        "marginBorrow": {"status": "AVAILABLE", "value": 1.2},
        "liquidationMaxPain": {"status": "AVAILABLE", "value": 98000},
        "fundFlows": {"status": "AVAILABLE", "summaries": [{"asset": "BTC", "latest": 12}]},
    }


def test_imported_overview_returns_all_six_legacy_style_fields_without_raw_payload():
    overview = build_imported_overview(_briefing(), checksum="a" * 64, market="all")

    assert overview["status"] == "PARTIAL"
    assert overview["market"] == "all"
    assert overview["asOf"] == "2026-08-25"
    assert [item["symbol"] for item in overview["opinions"]] == ["BTC", "HPG", "XAU"]
    assert overview["opinions"][0]["market"] == "crypto"
    assert overview["opinions"][1]["market"] == "vn"
    assert overview["opinions"][2]["market"] == "gold"
    assert overview["opinions"][0]["evidence"] == []
    assert overview["portfolioChanges"][0]["reason"] == "Quant change"
    assert overview["primary"]["thesis"] == "Portfolio remains diversified"
    assert overview["riskAlerts"][0]["symbol"] == "HPG"
    assert overview["portfolioState"]["currency"] == "USD"
    assert "supportingEvidenceIds" not in overview["opinions"][0]
    assert "payload" not in overview


def test_imported_overview_filters_the_personal_briefing_by_market():
    overview = build_imported_overview(_briefing(), checksum="b" * 64, market="vn")

    assert overview["market"] == "vn"
    assert [item["symbol"] for item in overview["opinions"]] == ["HPG"]


def test_imported_crypto_pulse_preserves_source_provenance_and_calendar():
    pulse = build_imported_crypto_market_pulse(
        _pulse(),
        {"events": [{"event": "US CPI", "eventAt": "2026-08-25T13:30:00Z", "impact": "high", "sourceCode": "cryptocraft"}]},
        checksum="c" * 64,
        mode="live",
    )

    assert pulse["mode"] == "live"
    assert pulse["tabs"]["overview"]["fearGreed"]["status"] == "AVAILABLE"
    assert pulse["tabs"]["overview"]["fearGreed"]["latest"]["value"] == 66
    assert pulse["tabs"]["flows"]["etfFlows"]["summaries"][0]["asset"] == "BTC"
    assert pulse["tabs"]["cycle"]["status"] == "AVAILABLE"
    assert pulse["tabs"]["flows"]["fundFlows"]["summaries"][0]["asset"] == "BTC"
    assert pulse["tabs"]["sentimentDerivatives"]["derivatives"]["status"] == "AVAILABLE"
    assert "btcBottom" not in pulse["tabs"]
    assert pulse["calendar"]["events"][0] == {
        "effectiveAt": "2026-08-25T13:30:00Z",
        "event": "US CPI",
        "impact": "high",
        "source": "cryptocraft",
    }


def test_imported_crypto_pulse_is_enriched_by_runtime_onchain_without_overwriting_import():
    imported = build_imported_crypto_market_pulse(
        _pulse(), {}, checksum="c" * 64, mode="live"
    )
    runtime = {
        "generatedAt": "2026-08-26T01:00:00Z",
        "status": "PARTIAL",
        "tabs": {
            "onchain": {
                "status": "AVAILABLE",
                "sources": [{"source": "defillama-chains", "sourceUrl": "https://api.llama.fi/v2/chains"}],
                "metrics": [{"metric": "crypto.chain.tvl_usd", "value": 123}],
                "series": [{"effectiveAt": "2026-08-26", "value": 123}],
            },
            "cycle": {
                "status": "AVAILABLE",
                "sources": [{"source": "cbbi-public", "sourceUrl": "https://example.test/cbbi"}],
                "metrics": [{"metric": "crypto.cycle.cbbi.confidence", "value": 54}],
                "series": [{"effectiveAt": "2026-08-26", "value": 54}],
            },
        },
        "calendar": {"status": "UNAVAILABLE", "events": [], "sources": []},
    }

    merged = merge_imported_crypto_market_pulse(imported, runtime)

    assert merged["tabs"]["overview"]["fearGreed"]["latest"]["value"] == 66
    assert merged["tabs"]["onchain"]["status"] == "AVAILABLE"
    assert merged["tabs"]["onchain"]["metrics"][0]["metric"] == "crypto.chain.tvl_usd"
    assert merged["tabs"]["onchain"]["dataOrigin"] == "legacy-import+live-observations"
    assert merged["dataLineage"]["runtimeTabs"] == ["cycle", "onchain"]
