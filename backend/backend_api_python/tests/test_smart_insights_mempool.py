from __future__ import annotations

import json
from datetime import datetime, timezone

from app.services.smart_insights.mempool import MempoolCollector
from app.services.smart_insights.transport import HttpResponse


class _Transport:
    def fetch(self, url: str, *, timeout_seconds: float, max_bytes: int, headers=None):
        del timeout_seconds, max_bytes, headers
        bodies = {
            "https://mempool.space/api/v1/fees/recommended": {"fastestFee": 8, "halfHourFee": 6, "hourFee": 4, "minimumFee": 1},
            "https://mempool.space/api/mempool": {"count": 1234, "vsize": 123456, "total_fee": 98765},
            "https://mempool.space/api/v1/mining/hashrate/3y": {"hashrates": [[1_777_000_000, 700_000_000_000_000_000_000]]},
            "https://mempool.space/api/blocks/tip/height": "910000",
        }
        body = bodies[url]
        raw = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
        return HttpResponse(status=200, url=url, body=raw)


def test_mempool_collects_current_block_height_for_halving_context() -> None:
    rows = MempoolCollector(transport=_Transport()).collect(
        datetime(2026, 8, 30, tzinfo=timezone.utc)
    )

    height = next(row for row in rows if row.value["metric"] == "crypto.chain.block_height")
    assert height.value["value"] == "910000"
    assert height.value["unit"] == "count"
    assert height.value["dimensions"]["network"] == "bitcoin"
