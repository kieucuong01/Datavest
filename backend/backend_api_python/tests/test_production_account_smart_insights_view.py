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
            "sourceCodes": ["farside-btc-etf", "farside-eth-etf", "farside-sol-etf"],
            "summaries": [{"asset": "BTC", "latest": 501500000, "effectiveAt": "2026-08-25"}],
            "series": [{"effectiveAt": "2026-08-24T00:00:00Z", "btc": 1200000, "eth": -250000, "sol": 80000, "total": 1030000}],
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
    assert pulse["tabs"]["flows"]["etfFlows"]["series"] == [
        {"effectiveAt": "2026-08-24T00:00:00Z", "value": 1200000, "symbol": "BTC", "source": "farside-btc-etf"},
        {"effectiveAt": "2026-08-24T00:00:00Z", "value": -250000, "symbol": "ETH", "source": "farside-eth-etf"},
        {"effectiveAt": "2026-08-24T00:00:00Z", "value": 80000, "symbol": "SOL", "source": "farside-sol-etf"},
    ]
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


def test_runtime_fear_greed_history_replaces_short_legacy_series_for_range_controls():
    imported = {
        "tabs": {
            "overview": {"status": "AVAILABLE", "sources": [], "fearGreed": {"status": "AVAILABLE", "sources": [{"source": "datavest-production-import"}], "series": [{"effectiveAt": "2026-08-01", "value": 30}]}},
            "sentimentDerivatives": {"status": "AVAILABLE", "sources": [], "fearGreed": {"status": "AVAILABLE", "sources": [{"source": "datavest-production-import"}], "series": [{"effectiveAt": "2026-08-01", "value": 30}]}},
        },
        "calendar": {"status": "UNAVAILABLE", "events": [], "sources": []},
    }
    runtime_fear = {
        "status": "AVAILABLE",
        "sources": [{"source": "alternative-fng", "sourceUrl": "https://api.alternative.me/fng/?limit=0&format=json"}],
        "series": [
            {"effectiveAt": "2018-02-01T00:00:00+00:00", "value": 40, "source": "alternative-fng"},
            {"effectiveAt": "2026-08-30T00:00:00+00:00", "value": 69, "source": "alternative-fng"},
        ],
        "latest": {"effectiveAt": "2026-08-30T00:00:00+00:00", "value": 69, "source": "alternative-fng"},
    }
    runtime = {
        "generatedAt": "2026-08-30T00:00:00+00:00",
        "status": "PARTIAL",
        "tabs": {
            "overview": {"status": "AVAILABLE", "sources": runtime_fear["sources"], "metrics": [], "fearGreed": runtime_fear},
            "sentimentDerivatives": {"status": "AVAILABLE", "sources": runtime_fear["sources"], "metrics": [], "fearGreed": runtime_fear},
        },
        "calendar": {"status": "UNAVAILABLE", "events": [], "sources": []},
    }

    merged = merge_imported_crypto_market_pulse(imported, runtime)

    for tab in ("overview", "sentimentDerivatives"):
        assert merged["tabs"][tab]["fearGreed"]["series"] == runtime_fear["series"]
        assert merged["tabs"][tab]["fearGreed"]["latest"] == runtime_fear["latest"]


def test_runtime_etf_history_merges_legacy_assets_and_prefers_cryptoetf_on_overlap():
    imported = {
        "tabs": {
            "overview": {
                "status": "AVAILABLE",
                "sources": [],
                "etfFlows": {
                    "status": "AVAILABLE",
                    "sources": [{"source": "farside-btc-etf"}],
                    "series": [
                        {"effectiveAt": "2026-08-20T00:00:00+00:00", "value": 1, "symbol": "BTC", "source": "farside-btc-etf"},
                        {"effectiveAt": "2026-08-20T00:00:00+00:00", "value": 2, "symbol": "ETH", "source": "farside-eth-etf"},
                    ],
                    "summaries": [{"asset": "BTC", "latest": 1}],
                },
            },
            "flows": {
                "status": "AVAILABLE",
                "sources": [],
                "etfFlows": {
                    "status": "AVAILABLE",
                    "sources": [{"source": "farside-btc-etf"}],
                    "series": [
                        {"effectiveAt": "2026-08-20T00:00:00+00:00", "value": 1, "symbol": "BTC", "source": "farside-btc-etf"},
                        {"effectiveAt": "2026-08-20T00:00:00+00:00", "value": 2, "symbol": "ETH", "source": "farside-eth-etf"},
                    ],
                    "summaries": [{"asset": "BTC", "latest": 1}],
                },
                "fundFlows": {"status": "UNAVAILABLE", "sources": [], "series": []},
            },
        },
        "calendar": {"status": "UNAVAILABLE", "events": [], "sources": []},
    }
    runtime_etf = {
        "status": "AVAILABLE",
        "sources": [{"source": "cryptoetf-btc-etf", "sourceUrl": "https://cryptoetf.today"}],
        "series": [
            {"effectiveAt": "2026-08-20T00:00:00+00:00", "value": 21040446.43, "symbol": "BTC", "source": "cryptoetf-btc-etf"},
            {"effectiveAt": "2026-08-28T00:00:00+00:00", "value": 901.5, "symbol": "SOL", "source": "cryptoetf-sol-etf"},
        ],
        "summaries": [{"asset": "BTC", "latest": 21040446.43, "effectiveAt": "2026-08-20T00:00:00+00:00"}],
    }
    runtime = {
        "generatedAt": "2026-08-30T00:00:00+00:00",
        "status": "PARTIAL",
        "tabs": {
            "overview": {"status": "AVAILABLE", "sources": runtime_etf["sources"], "metrics": [], "etfFlows": runtime_etf},
            "flows": {"status": "AVAILABLE", "sources": runtime_etf["sources"], "metrics": [], "etfFlows": runtime_etf, "fundFlows": {"status": "UNAVAILABLE", "sources": [], "series": []}},
        },
        "calendar": {"status": "UNAVAILABLE", "events": [], "sources": []},
    }

    merged = merge_imported_crypto_market_pulse(imported, runtime)

    for tab in ("overview", "flows"):
        series = merged["tabs"][tab]["etfFlows"]["series"]
        assert series == [
            runtime_etf["series"][0],
            {"effectiveAt": "2026-08-20T00:00:00+00:00", "value": 2, "symbol": "ETH", "source": "farside-eth-etf"},
            runtime_etf["series"][1],
        ]
        assert {item["asset"] for item in merged["tabs"][tab]["etfFlows"]["summaries"]} == {"BTC", "ETH", "SOL"}
