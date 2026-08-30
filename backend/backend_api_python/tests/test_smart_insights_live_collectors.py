from __future__ import annotations

import json
from datetime import datetime, timezone

from app.services.smart_insights.coinmetrics import CoinMetricsCollector
from app.services.smart_insights.defillama import DefiLlamaChainsCollector
from app.services.smart_insights.transport import HttpResponse


class _Transport:
    def __init__(self, body: object, *, url: str) -> None:
        self.body = json.dumps(body).encode("utf-8")
        self.url = url
        self.calls: list[str] = []

    def fetch(self, url: str, *, timeout_seconds: float, max_bytes: int, headers=None):
        del timeout_seconds, max_bytes, headers
        self.calls.append(url)
        return HttpResponse(status=200, url=url, body=self.body)


AS_OF = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def test_defillama_chains_preserves_chain_rows_and_total() -> None:
    url = "https://api.llama.fi/v2/chains"
    transport = _Transport(
        [{"name": "Ethereum", "tvl": 123.4, "tokenSymbol": "ETH"}], url=url
    )

    rows = DefiLlamaChainsCollector(transport=transport).collect(AS_OF)

    assert transport.calls == [url]
    assert [row.value["metric"] for row in rows] == [
        "crypto.defi.chain_tvl_usd",
        "crypto.defi.chain_tvl_usd",
    ]
    assert rows[0].value["dimensions"]["chain"] == "Ethereum"
    assert rows[1].value["dimensions"]["chain"] == "TOTAL"
    assert rows[1].value["value"] == "123.4"


def test_coinmetrics_maps_daily_provider_metrics_to_btc_observations() -> None:
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    transport = _Transport(
        {
            "data": [
                {
                    "asset": "btc",
                    "time": "2026-08-25T00:00:00.000000000Z",
                    "AdrActCnt": "1000",
                    "CapMVRVCur": "1.25",
                }
            ],
            "next_page_url": None,
        },
        url=url,
    )

    rows = CoinMetricsCollector(transport=transport).collect(AS_OF)

    assert len(rows) == 2
    assert {row.value["metric"] for row in rows} == {
        "crypto.onchain.active_addresses",
        "crypto.onchain.mvrv",
    }
    assert all(row.symbol == "BTC" for row in rows)
    assert all(row.value["dimensions"]["frequency"] == "daily" for row in rows)
