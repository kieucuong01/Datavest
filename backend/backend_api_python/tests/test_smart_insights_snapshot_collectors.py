from __future__ import annotations

from datetime import datetime, timezone

from app.services.smart_insights.browser_snapshots import write_snapshot


NOW = datetime(2026, 8, 30, 2, 0, tzinfo=timezone.utc)


def _payload(source_code: str, records: list[dict[str, str]]) -> dict[str, object]:
    return {
        "source": source_code,
        "source_url": "https://example.test/source",
        "schema_version": 1,
        "fetched_at": NOW.isoformat(),
        "coverage": {
            "record_count": len(records),
            "oldest_effective_at": records[0]["effective_at"],
            "newest_effective_at": records[-1]["effective_at"],
        },
        "records": records,
    }


def test_snapshot_collector_normalizes_etf_and_coinshares_records(tmp_path):
    from app.services.smart_insights.snapshot_collectors import SnapshotObservationCollector

    write_snapshot(
        "farside-btc-etf",
        _payload("farside-btc-etf", [{
            "effective_at": "2026-08-29T00:00:00+00:00",
            "metric": "crypto.etf.net_flow_usd",
            "value": "123000000",
            "unit": "USD",
            "asset": "BTC",
            "fund": "TOTAL",
        }]),
        root=tmp_path,
    )
    write_snapshot(
        "coinshares-weekly",
        _payload("coinshares-weekly", [{
            "effective_at": "2026-08-25T00:00:00+00:00",
            "metric": "crypto.coinshares.net_flow_usd",
            "value": "1000000000",
            "unit": "USD",
            "dimension": "total",
            "label": "Total",
        }]),
        root=tmp_path,
    )

    etf = SnapshotObservationCollector("farside-btc-etf", root=tmp_path, clock=lambda: NOW).collect()
    coinshares = SnapshotObservationCollector("coinshares-weekly", root=tmp_path, clock=lambda: NOW).collect()

    assert etf[0].value["metric"] == "crypto.etf.net_flow_usd"
    assert etf[0].symbol == "BTC"
    assert etf[0].value["dimensions"] == {"asset": "BTC", "fund": "TOTAL"}
    assert coinshares[0].value["metric"] == "crypto.coinshares.net_flow_usd"
    assert coinshares[0].symbol is None
    assert coinshares[0].value["dimensions"] == {"dimension": "total", "label": "Total"}


def test_snapshot_collector_accepts_an_extended_cryptoetf_asset(tmp_path):
    from app.services.smart_insights.snapshot_collectors import SnapshotObservationCollector

    write_snapshot(
        "cryptoetf-xrp-etf",
        _payload("cryptoetf-xrp-etf", [{
            "effective_at": "2026-08-29T00:00:00+00:00",
            "metric": "crypto.etf.net_flow_usd",
            "value": "18000000",
            "unit": "USD",
            "asset": "XRP",
            "fund": "TOTAL",
        }]),
        root=tmp_path,
    )

    records = SnapshotObservationCollector("cryptoetf-xrp-etf", root=tmp_path, clock=lambda: NOW).collect()

    assert records[0].symbol == "XRP"


def test_snapshot_collector_preserves_bitinfocharts_address_dimensions(tmp_path):
    from app.services.smart_insights.snapshot_collectors import SnapshotObservationCollector

    write_snapshot(
        "bitinfocharts-top-addresses",
        _payload("bitinfocharts-top-addresses", [{
            "effective_at": "2026-08-30T00:00:00+00:00",
            "metric": "crypto.large_address.address_balance_btc",
            "value": "1500",
            "unit": "BTC",
            "symbol": "BTC",
            "address": "bc1qexampleaddress",
            "rank": "2",
            "cohort": "reviewed_non_exchange",
            "quality_tier": "heuristic",
        }]),
        root=tmp_path,
    )

    records = SnapshotObservationCollector("bitinfocharts-top-addresses", root=tmp_path, clock=lambda: NOW).collect()

    assert records[0].symbol == "BTC"
    assert records[0].value["dimensions"] == {
        "address": "bc1qexampleaddress", "rank": "2",
        "cohort": "reviewed_non_exchange", "quality_tier": "heuristic",
    }


def test_registry_reads_snapshot_collectors_for_the_seven_browser_sources(monkeypatch, tmp_path):
    monkeypatch.setenv("CRYPTO_INSIGHTS_SNAPSHOT_ROOT", str(tmp_path))
    from app.services.smart_insights.collectors import default_collector_registry

    registry = default_collector_registry()
    expected = {
        "alternative-fng",
        "farside-btc-etf",
        "farside-eth-etf",
        "farside-sol-etf",
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
        "coinshares-weekly",
        "blockchaincenter-altcoin-season",
        "bitinfocharts-top-addresses",
    }
    assert all(registry[code].__module__.endswith("snapshot_collectors") for code in expected)
