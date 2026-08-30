"""Golden contracts for public macro and on-chain collectors."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json

import pytest


NOW = datetime(2026, 8, 13, 13, 0, tzinfo=timezone.utc)


class Response:
    def __init__(self, url: str, body: bytes) -> None:
        self.status = 200
        self.url = url
        self.body = body


class Transport:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")
        self.calls = []

    def fetch(self, url, *, timeout_seconds, max_bytes):
        self.calls.append((url, timeout_seconds, max_bytes))
        return Response(url, self.body)


def test_fred_public_csv_port_skips_missing_values_and_keeps_safe_provenance():
    from app.services.smart_insights.fred import FredCollector

    transport = Transport(
        "observation_date,DGS10\n"
        "2026-08-10,4.25\n"
        "2026-08-11,\n"
        "2026-08-12,.\n"
        "2026-08-13,4.32\n"
    )
    rows = FredCollector(transport=transport, clock=lambda: NOW).collect(
        "DGS10", date(2026, 8, 10), date(2026, 8, 13)
    )

    assert [row.value["value"] for row in rows] == ["4.25", "4.32"]
    assert {row.value["metric"] for row in rows} == {"macro.yield.10y_pct"}
    assert rows[-1].effective_at == datetime(2026, 8, 13, tzinfo=timezone.utc)
    assert rows[-1].source_url == "https://fred.stlouisfed.org/graph/fredgraph.csv"
    assert transport.calls[0][0].endswith("id=DGS10&cosd=2026-08-10&coed=2026-08-13")

    with pytest.raises(ValueError, match="allow-listed"):
        FredCollector(transport=transport).collect("EVIL", date(2026, 8, 10), date(2026, 8, 13))


def test_defillama_stablecoin_port_normalizes_closed_daily_series():
    from app.services.smart_insights.defillama import DefiLlamaStablecoinsCollector

    payload = [
        {"date": "1786492800", "totalCirculatingUSD": {"peggedUSD": 150_000_000_000, "peggedEUR": 3_000_000_000}},
        {"date": "1786579200", "totalCirculatingUSD": {"peggedUSD": 151_000_000_000, "peggedEUR": 3_100_000_000}},
        {"date": "1786665600", "totalCirculatingUSD": {"peggedUSD": 999}},
    ]
    rows = DefiLlamaStablecoinsCollector(
        transport=Transport(json.dumps(payload))
    ).collect(datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc))

    assert [row.value["value"] for row in rows] == ["153000000000", "154100000000"]
    assert {row.value["metric"] for row in rows} == {"crypto.stablecoin.supply_usd"}
    assert all(row.data_class.value == "LIVE" for row in rows)


def test_defillama_rejects_negative_values_fail_closed():
    from app.services.smart_insights.collectors import CollectorUnavailable
    from app.services.smart_insights.defillama import DefiLlamaStablecoinsCollector

    payload = [{"date": "1786492800", "totalCirculatingUSD": {"peggedUSD": -1}}]
    with pytest.raises(CollectorUnavailable, match="INVALID_VALUE"):
        DefiLlamaStablecoinsCollector(transport=Transport(json.dumps(payload))).collect(
            datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc)
        )


def test_legacy_fear_greed_and_mempool_collectors_keep_source_backed_observations():
    from app.services.smart_insights.alternative_fng import AlternativeFearGreedCollector
    from app.services.smart_insights.mempool import MempoolCollector

    fear_rows = AlternativeFearGreedCollector(
        transport=Transport(
            json.dumps(
                {
                    "data": [
                        {"value": "66", "value_classification": "Greed", "timestamp": "1786492800"},
                        {"value": "70", "value_classification": "Greed", "timestamp": "1786579200"},
                    ]
                }
            )
        )
    ).collect(datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc))
    assert [row.value["value"] for row in fear_rows] == ["66", "70"]
    assert all(row.value["metric"] == "crypto.fear_greed.index" for row in fear_rows)

    class MempoolTransport:
        def fetch(self, url, *, timeout_seconds, max_bytes):
            payloads = {
                "https://mempool.space/api/v1/fees/recommended": {"fastestFee": 12, "halfHourFee": 8, "hourFee": 5, "minimumFee": 1},
                "https://mempool.space/api/mempool": {"count": 190234, "vsize": 20000000, "total_fee": 123456},
                "https://mempool.space/api/v1/mining/hashrate/3y": {"hashrates": [[1786492800, 800000000000000000]], "difficulty": []},
            }
            return Response(url, json.dumps(payloads[url]).encode("utf-8"))

    mempool_rows = MempoolCollector(transport=MempoolTransport()).collect(NOW)
    assert {row.value["metric"] for row in mempool_rows} >= {
        "crypto.mempool.tx_count",
        "crypto.mempool.fastest_fee_sat_vb",
        "crypto.mining.hashrate_hs",
    }
    assert all(row.source_code == "mempool-space" for row in mempool_rows)


def test_farside_collector_accepts_total_rows_and_rejects_malformed_tables():
    from app.services.smart_insights.collectors import CollectorUnavailable
    from app.services.smart_insights.farside import FarsideEtfCollector

    html = """
      <table><tr><th>Date</th><th>IBIT</th><th>Total</th></tr>
      <tr><td>13 Aug 2026</td><td>501.0</td><td>501.0</td></tr></table>
    """
    rows = FarsideEtfCollector("BTC", transport=Transport(html)).collect(
        datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc)
    )
    assert [float(row.value["value"]) for row in rows] == [501000000.0]
    assert rows[0].value["dimensions"]["fund"] == "TOTAL"

    with pytest.raises(CollectorUnavailable, match="SCHEMA_DRIFT"):
        FarsideEtfCollector("BTC", transport=Transport("<html>no table</html>")).collect(NOW)


def test_cycle_collectors_port_cbbi_json_and_altcoin_season_page():
    from app.services.smart_insights.cycle import AltcoinSeasonCollector, CbbiCollector

    cbbi = CbbiCollector(
        transport=Transport(
            json.dumps(
                {
                    "Confidence": {"1786492800": 0.30, "1786579200": 0.42},
                    "PiCycle": {"1786492800": 0.2, "1786579200": 0.3},
                }
            )
        )
    ).collect(datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc))
    assert len(cbbi) == 4
    assert {row.value["metric"] for row in cbbi} == {
        "crypto.cycle.cbbi.confidence",
        "crypto.cycle.cbbi.component.pi_cycle",
    }

    html = """
      <button>Altcoin Season (61)</button><button>Month (43)</button><button>Year (37)</button>
    """
    altcoin = AltcoinSeasonCollector(transport=Transport(html)).collect(
        datetime(2026, 8, 14, 13, 0, tzinfo=timezone.utc)
    )
    assert {row.value["metric"] for row in altcoin} == {
        "crypto.cycle.altcoin_season.index",
        "crypto.cycle.altcoin_season.month_index",
        "crypto.cycle.altcoin_season.year_index",
    }


def test_public_collectors_are_registered_without_api_keys():
    from app.services.smart_insights.collectors import default_collector_registry

    registry = default_collector_registry()
    assert {"fred", "defillama-stablecoins", "alternative-fng", "mempool-space", "farside-btc-etf", "cbbi-public", "blockchaincenter-altcoin-season"} <= set(registry)
