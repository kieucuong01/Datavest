from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _observation(
    source: str,
    metric: str,
    value: str,
    *,
    effective_at: str = "2026-08-24T00:00:00+00:00",
    symbol: str | None = None,
    dimensions: dict | None = None,
):
    return {
        "id": f"{source}-{metric}-{symbol or 'global'}-{effective_at}",
        "source": source,
        "sourceUrl": f"https://example.test/{source}",
        "market": "crypto" if source != "cryptocraft" else "macro",
        "symbol": symbol,
        "effectiveAt": effective_at,
        "observedAt": "2026-08-25T01:00:00+00:00",
        "methodologyVersion": f"{source}-v1",
        "dataClass": "LIVE",
        "checksum": "a" * 64,
        "warnings": [],
        "value": {
            "metric": metric,
            "value": value,
            "unit": "USD" if "flow" in metric else "index",
            "dimensions": dimensions or {},
        },
    }


def test_crypto_pulse_groups_persisted_evidence_by_legacy_tab_without_inventing_values():
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation("alternative-fng", "crypto.fear_greed.index", "66"),
        _observation("farside-btc-etf", "crypto.etf.net_flow_usd", "501000000", symbol="BTC", dimensions={"fund": "TOTAL"}),
        _observation("farside-eth-etf", "crypto.etf.net_flow_usd", "12000000", symbol="ETH", dimensions={"fund": "TOTAL"}),
        _observation("defillama-stablecoins", "crypto.stablecoin.supply_usd", "180000000000"),
        _observation("mempool-space", "crypto.mempool.tx_count", "190234"),
        _observation("blockchaincenter-altcoin-season", "crypto.cycle.altcoin_season.index", "41"),
        _observation("cryptocraft", "macro.calendar.event", "1", dimensions={"event": "US CPI", "impact": "high"}),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            assert data_class == "LIVE"
            assert as_of is None
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    assert result["mode"] == "live"
    assert result["status"] == "AVAILABLE"
    assert result["tabs"]["sentimentDerivatives"]["fearGreed"]["latest"]["value"] == 66
    assert result["tabs"]["flows"]["etfFlows"]["summaries"] == [
        {"asset": "BTC", "latest": 501000000.0, "effectiveAt": "2026-08-24T00:00:00+00:00"},
        {"asset": "ETH", "latest": 12000000.0, "effectiveAt": "2026-08-24T00:00:00+00:00"},
    ]
    assert {item["metric"] for item in result["tabs"]["onchain"]["metrics"]} == {
        "crypto.mempool.tx_count",
        "crypto.stablecoin.supply_usd",
    }
    assert result["tabs"]["flows"]["whaleFlows"]["status"] == "UNAVAILABLE"
    assert "btcBottom" not in result["tabs"]
    assert result["calendar"]["events"] == [
        {"effectiveAt": "2026-08-24T00:00:00+00:00", "event": "US CPI", "impact": "high", "source": "cryptocraft"}
    ]


def test_crypto_pulse_exposes_requested_date_and_readiness_contract():
    from app.services.smart_insights.service import SmartInsightsService

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            assert data_class == "LIVE"
            assert as_of == "2026-08-24"
            return [_observation("alternative-fng", "crypto.fear_greed.index", "66")]

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of="2026-08-24", mode="live"
    )

    assert result["requestedAsOf"] == "2026-08-24"
    assert result["resolvedAsOf"] == "2026-08-24"
    assert result["fetchedAt"].endswith("+07:00")
    assert result["freshness"] in {"FRESH", "PARTIAL"}
    assert result["coverage"]["totalTabs"] == 5


def test_crypto_pulse_merges_confirmed_whale_accumulation_into_flows_not_a_separate_tab():
    """A non-exchange balance increase is only bullish when exchange netflow confirms outflow."""
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation(
            "bitinfocharts-top-addresses",
            "crypto.large_address.balance_change_btc",
            "1250",
            symbol="BTC",
            dimensions={"cohort": "reviewed_non_exchange", "quality_tier": "heuristic", "label_coverage": "0.67"},
        ),
        _observation(
            "bitinfocharts-top-addresses",
            "crypto.large_address.reviewed_non_exchange_balance_btc",
            "2100000",
            symbol="BTC",
            dimensions={"cohort": "reviewed_non_exchange", "quality_tier": "heuristic", "label_coverage": "0.67"},
        ),
        _observation(
            "bitinfocharts-top-addresses",
            "crypto.large_address.label_coverage",
            "0.67",
            symbol="BTC",
            dimensions={"cohort": "reviewed_non_exchange", "quality_tier": "heuristic"},
        ),
        _observation("coinmetrics-community", "crypto.onchain.exchange_netflow_native", "-800", symbol="BTC"),
        _observation("coinmetrics-community", "crypto.onchain.exchange_reserve_native", "2500000", symbol="BTC"),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    flows = result["tabs"]["flows"]
    assert "whales" not in result["tabs"]
    assert flows["whaleFlows"]["status"] == "AVAILABLE"
    assert flows["whaleFlows"]["insight"] == {
        "tone": "ACCUMULATION",
        "confidence": "MEDIUM",
        "reasonMetrics": [
            "crypto.large_address.balance_change_btc",
            "crypto.onchain.exchange_netflow_native",
        ],
    }
    assert flows["whaleFlows"]["quality"]["labelCoverage"] == 0.67
    assert flows["whaleFlows"]["cohort"]["latestChange"]["value"] == 1250.0
    assert flows["whaleFlows"]["exchangePressure"]["latestNetflow"]["value"] == -800.0


def test_crypto_pulse_marks_whale_signal_mixed_when_cohort_and_exchange_evidence_are_different_days():
    """A stale cohort cannot confirm a newer exchange-flow observation."""
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation("bitinfocharts-top-addresses", "crypto.large_address.balance_change_btc", "1250", symbol="BTC", effective_at="2026-08-24T00:00:00+00:00"),
        _observation("coinmetrics-community", "crypto.onchain.exchange_netflow_native", "-800", symbol="BTC", effective_at="2026-08-30T00:00:00+00:00"),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    assert result["tabs"]["flows"]["whaleFlows"]["insight"] == {
        "tone": "MIXED",
        "confidence": "LOW",
        "reasonMetrics": [
            "crypto.large_address.balance_change_btc",
            "crypto.onchain.exchange_netflow_native",
        ],
    }


def test_crypto_pulse_exposes_whale_movers_and_concentration_from_address_history():
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.reviewed_non_exchange_balance_btc", "2600",
            symbol="BTC", dimensions={"quality_tier": "heuristic", "label_coverage": "0.5"},
        ),
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.balance_change_btc", "40",
            symbol="BTC", dimensions={"quality_tier": "heuristic", "label_coverage": "0.5"},
        ),
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.matched_balance_change_btc", "40",
            symbol="BTC", dimensions={"quality_tier": "heuristic"},
        ),
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.balance_increase_btc", "100",
            symbol="BTC", dimensions={"quality_tier": "heuristic"},
        ),
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.balance_decrease_btc", "-60",
            symbol="BTC", dimensions={"quality_tier": "heuristic"},
        ),
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.top10_share", "0.72",
            symbol="BTC", dimensions={"quality_tier": "heuristic"},
        ),
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.address_balance_btc", "1500",
            symbol="BTC", dimensions={"address": "bc1qaccumulator", "rank": "2", "entity_category": "unknown"},
        ),
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.address_balance_change_btc", "100",
            symbol="BTC", dimensions={"address": "bc1qaccumulator", "rank": "2", "entity_category": "unknown"},
        ),
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.address_balance_btc", "1100",
            symbol="BTC", dimensions={"address": "bc1qdistributor", "rank": "7", "entity_category": "reviewed_other"},
        ),
        _observation(
            "bitinfocharts-top-addresses", "crypto.large_address.address_balance_change_btc", "-60",
            symbol="BTC", dimensions={"address": "bc1qdistributor", "rank": "7", "entity_category": "reviewed_other"},
        ),
        _observation("coinmetrics-community", "crypto.onchain.exchange_netflow_native", "-80", symbol="BTC"),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    whale = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )["tabs"]["flows"]["whaleFlows"]

    assert whale["cohort"]["latestTop10Share"]["value"] == 0.72
    assert whale["quality"]["matchedAddressCount"] is None
    assert whale["movers"]["accumulating"][0]["address"] == "bc1qaccumulator"
    assert whale["movers"]["distributing"][0]["address"] == "bc1qdistributor"


def test_crypto_pulse_rejects_demo_evidence_and_keeps_empty_tabs_unavailable():
    from app.services.smart_insights.service import SmartInsightsService

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            assert data_class == "DEMO"
            return []

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of="2026-08-24", mode="demo"
    )

    assert result["status"] == "UNAVAILABLE"
    assert {tab["status"] for tab in result["tabs"].values()} == {"UNAVAILABLE"}
    assert result["calendar"]["events"] == []


def test_crypto_pulse_exposes_persisted_coinshares_as_fund_flows():
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation(
            "coinshares-weekly", "crypto.coinshares.net_flow_usd", "1030000000",
            effective_at="2026-08-25T00:00:00+00:00",
            dimensions={"dimension": "total", "label": "Total"},
        )
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    assert result["tabs"]["flows"]["status"] == "AVAILABLE"
    assert result["tabs"]["flows"]["fundFlows"]["summaries"] == [
        {"asset": "Total", "latest": 1030000000.0, "effectiveAt": "2026-08-25T00:00:00+00:00"}
    ]


def test_crypto_pulse_keeps_time_series_points_for_charts():
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation("alternative-fng", "crypto.fear_greed.index", "31", effective_at="2026-08-23T00:00:00+00:00"),
        _observation("alternative-fng", "crypto.fear_greed.index", "66", effective_at="2026-08-24T00:00:00+00:00"),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    assert result["tabs"]["sentimentDerivatives"]["fearGreed"]["series"] == [
        {"effectiveAt": "2026-08-23T00:00:00+00:00", "value": 31.0, "metric": "crypto.fear_greed.index", "symbol": None, "source": "alternative-fng"},
        {"effectiveAt": "2026-08-24T00:00:00+00:00", "value": 66.0, "metric": "crypto.fear_greed.index", "symbol": None, "source": "alternative-fng"},
    ]


def test_crypto_pulse_keeps_full_fear_greed_history_for_range_controls():
    from app.services.smart_insights.service import SmartInsightsService

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        _observation(
            "alternative-fng", "crypto.fear_greed.index", str(20 + day % 60),
            effective_at=(start + timedelta(days=day)).isoformat(),
        )
        for day in range(400)
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    assert len(result["tabs"]["sentimentDerivatives"]["fearGreed"]["series"]) == 400


def test_crypto_pulse_keeps_long_derivatives_history_for_terminal_ranges():
    from app.services.smart_insights.service import SmartInsightsService

    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = [
        _observation(
            "binance-usdm-derivatives", "crypto.derivatives.perpetual.funding_annualized", "0.1",
            symbol="BTC", effective_at=(start + timedelta(days=day)).isoformat(),
        )
        for day in range(365)
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    assert len(result["tabs"]["sentimentDerivatives"]["series"]) == 365


def test_crypto_pulse_filters_retired_cbbi_and_rhodl_metrics_from_the_read_model():
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation("blockchaincenter-altcoin-season", "crypto.cycle.altcoin_season.index", "41"),
        _observation("cbbi-public", "crypto.cycle.cbbi.confidence", "54"),
        _observation("coinmetrics-community", "crypto.onchain.rhodl_ratio", "0.72", symbol="BTC"),
        _observation("coinmetrics-community", "crypto.onchain.mvrv", "1.8", symbol="BTC"),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    cycle = result["tabs"]["cycle"]
    assert {point["metric"] for point in cycle["series"]} == {"crypto.cycle.altcoin_season.index"}
    assert "cbbi" not in cycle
    assert not any("cbbi" in point["metric"] for point in result["tabs"]["overview"]["metrics"])
    assert {point["metric"] for point in result["tabs"]["onchain"]["series"]} == {"crypto.onchain.mvrv"}


def test_crypto_pulse_separates_onchain_groups_and_excludes_market_prices():
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation("coinmetrics-community", "crypto.onchain.mvrv", "1.8", symbol="BTC"),
        _observation("coinmetrics-community", "crypto.onchain.exchange_reserve_native", "2500000", symbol="BTC"),
        _observation("coinmetrics-community", "crypto.onchain.exchange_netflow_native", "-1200", symbol="BTC"),
        _observation("defillama-stablecoins", "crypto.stablecoin.supply_usd", "180000000000"),
        _observation("mempool-space", "crypto.mempool.fastest_fee_sat_vb", "5", symbol="BTC"),
        _observation("coinmetrics-community", "crypto.mining.hashrate_hs", "700000000000000000000", symbol="BTC"),
        _observation("coinmetrics-community", "crypto.market.price_usd", "65000", symbol="BTC"),
        _observation("mempool-space", "crypto.chain.block_height", "910000", symbol="BTC"),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    onchain = result["tabs"]["onchain"]
    assert [group["key"] for group in onchain["groups"]] == [
        "valuation",
        "holders",
        "liquidity",
        "network",
    ]
    assert onchain["groups"][0]["status"] == "AVAILABLE"
    assert onchain["groups"][1]["status"] == "UNAVAILABLE"
    assert {item["metric"] for item in onchain["groups"][2]["metrics"]} == {
        "crypto.onchain.exchange_reserve_native",
        "crypto.onchain.exchange_netflow_native",
        "crypto.stablecoin.supply_usd",
    }
    assert {item["metric"] for item in onchain["groups"][3]["metrics"]} == {
        "crypto.mempool.fastest_fee_sat_vb",
        "crypto.mining.hashrate_hs",
        "crypto.chain.block_height",
    }
    assert "crypto.market.price_usd" not in {item["metric"] for item in onchain["metrics"]}
    assert "crypto.market.price_usd" not in {item["metric"] for item in onchain["series"]}
    assert result["tabs"]["cycle"]["halving"]["metrics"] == [
        {
            "metric": "crypto.chain.block_height",
            "value": 910000.0,
            "unit": "index",
            "symbol": "BTC",
            "effectiveAt": "2026-08-24T00:00:00+00:00",
            "source": "mempool-space",
            "evidenceId": "mempool-space-crypto.chain.block_height-BTC-2026-08-24T00:00:00+00:00",
        }
    ]
    assert result["tabs"]["cycle"]["priceHistory"]["series"] == [
        {
            "effectiveAt": "2026-08-24T00:00:00+00:00",
            "value": 65000.0,
            "metric": "crypto.market.price_usd",
            "symbol": "BTC",
            "source": "coinmetrics-community",
        }
    ]


def test_crypto_pulse_prefers_free_api_etf_points_without_duplicate_asset_dates():
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation("xoomar-btc-etf", "crypto.etf.net_flow_usd", "10000000", effective_at="2026-08-27T00:00:00+00:00", symbol="BTC", dimensions={"fund": "TOTAL"}),
        _observation("xoomar-btc-etf", "crypto.etf.net_flow_usd", "20000000", effective_at="2026-08-28T00:00:00+00:00", symbol="BTC", dimensions={"fund": "TOTAL"}),
        _observation("cryptoetf-btc-etf", "crypto.etf.net_flow_usd", "22000000", effective_at="2026-08-28T07:00:00+07:00", symbol="BTC", dimensions={"fund": "TOTAL"}),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    assert result["tabs"]["flows"]["etfFlows"]["series"] == [
        {"effectiveAt": "2026-08-27T00:00:00+00:00", "value": 10000000.0, "metric": "crypto.etf.net_flow_usd", "symbol": "BTC", "source": "xoomar-btc-etf"},
        {"effectiveAt": "2026-08-28T07:00:00+07:00", "value": 22000000.0, "metric": "crypto.etf.net_flow_usd", "symbol": "BTC", "source": "cryptoetf-btc-etf"},
    ]


def test_crypto_pulse_exposes_new_cryptoetf_assets_in_flow_summaries():
    from app.services.smart_insights.service import SmartInsightsService

    rows = [
        _observation("cryptoetf-xrp-etf", "crypto.etf.net_flow_usd", "18000000", symbol="XRP", dimensions={"fund": "TOTAL"}),
        _observation("cryptoetf-hyp-etf", "crypto.etf.net_flow_usd", "4500000", symbol="HYPE", dimensions={"fund": "TOTAL"}),
    ]

    class Repository:
        def list_pulse_observations(self, *, data_class, as_of):
            return rows

    result = SmartInsightsService(repository=Repository()).get_crypto_market_pulse(
        user_id=7, as_of=None, mode="live"
    )

    assert result["tabs"]["flows"]["etfFlows"]["summaries"] == [
        {"asset": "XRP", "latest": 18000000.0, "effectiveAt": "2026-08-24T00:00:00+00:00"},
        {"asset": "HYPE", "latest": 4500000.0, "effectiveAt": "2026-08-24T00:00:00+00:00"},
    ]


def test_crypto_pulse_route_requires_jwt_and_passes_validated_inputs(client, monkeypatch):
    from app.routes import smart_insights as routes

    captured = {}

    class Service:
        def get_crypto_market_pulse(self, *, user_id, as_of, mode):
            captured.update(user_id=user_id, as_of=as_of, mode=mode)
            return {"status": "UNAVAILABLE", "tabs": {}, "calendar": {"events": []}}

    monkeypatch.setattr(routes, "get_smart_insights_service", lambda: Service())

    unauthorized = client.get("/api/smart-insights/crypto-market-pulse")
    assert unauthorized.status_code == 401

    monkeypatch.setattr(
        "app.utils.auth.verify_token",
        lambda _raw: {
            "sub": "researcher",
            "user_id": 41,
            "role": "user",
            "_verified_username": "researcher",
            "_verified_user_role": "user",
        },
    )
    response = client.get(
        "/api/smart-insights/crypto-market-pulse?as_of=2026-08-24&mode=live",
        headers={"Authorization": "Bearer research-jwt"},
    )

    assert response.status_code == 200
    assert captured == {"user_id": 41, "as_of": "2026-08-24", "mode": "live"}
