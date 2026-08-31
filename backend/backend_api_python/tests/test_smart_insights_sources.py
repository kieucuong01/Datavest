from __future__ import annotations

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_registry_matches_documented_production_activation_set():
    from app.services.smart_insights.sources import (
        PRODUCTION_VERIFIED_SOURCE_CODES,
        SOURCES,
        UNQUALIFIED_SOURCE_REASONS,
    )

    assert len(PRODUCTION_VERIFIED_SOURCE_CODES) == 25
    assert PRODUCTION_VERIFIED_SOURCE_CODES <= set(SOURCES)
    assert set(UNQUALIFIED_SOURCE_REASONS) == {
        "mempool-btc-large-addresses",
        "cftc-legacy",
        "eia-energy",
    }
    assert all(SOURCES[code].enabled_by_default for code in PRODUCTION_VERIFIED_SOURCE_CODES)
    assert all(not SOURCES[code].enabled_by_default for code in UNQUALIFIED_SOURCE_REASONS)


def test_only_verified_sources_are_default_enabled_and_runtime_status_is_explicit():
    from app.services.smart_insights.sources import SOURCES

    assert {source.code for source in SOURCES.values() if source.enabled_by_default}
    assert {source.code for source in SOURCES.values() if source.activation_mode == "RUNTIME"} == {
        "alternative-fng",
        "binance-usdm-derivatives",
        "bitinfocharts-top-addresses",
        "blockchaincenter-altcoin-season",
        "bybit-derivatives",
        "cbbi-public",
        "coinmetrics-community",
        "coinglass-liquidation-maxpain",
        "coinglass-margin-borrow",
        "coinshares-weekly",
        "cryptoetf-btc-etf",
        "cryptoetf-eth-etf",
        "cryptoetf-sol-etf",
        "cryptoetf-xrp-etf",
        "cryptoetf-hyp-etf",
        "cryptoetf-doge-etf",
        "cryptoetf-link-etf",
        "cryptoetf-avax-etf",
        "cryptoetf-hbar-etf",
        "cryptoetf-ltc-etf",
        "cryptoetf-bnb-etf",
        "cryptoetf-dot-etf",
        "cryptoetf-sui-etf",
        "defillama-chains",
        "defillama-stablecoins",
        "deribit-public-derivatives",
        "farside-btc-etf",
        "farside-eth-etf",
        "farside-sol-etf",
        "mempool-space",
        "openbb-deribit",
        "fred",
        "xoomar-btc-etf",
        "xoomar-eth-etf",
    }
    assert all(
        source.disabled_reason
        for source in SOURCES.values()
        if source.activation_mode == "DISABLED"
    )


def test_activation_migration_enables_only_the_verified_set_and_allows_partial_runs():
    migration = (
        BACKEND_ROOT / "migrations" / "20260825_smart_insights_production_sources.sql"
    ).read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS activation_mode" in migration
    assert "enabled = EXCLUDED.enabled" in migration
    assert "'PARTIAL'" in migration
    assert "POSTGRES_PASSWORD" not in migration
