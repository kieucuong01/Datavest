from __future__ import annotations

from datetime import datetime, timezone


AS_OF = datetime(2026, 9, 2, 9, 30, tzinfo=timezone.utc)


class _KlineService:
    def get_kline(self, market, symbol, timeframe, limit):
        assert timeframe == "1D"
        assert limit == 21
        assert (market, symbol) in {
            ("Crypto", "LINK/USDT"),
            ("VNStock", "HPG"),
            ("Forex", "XAUUSD"),
        }
        return [
            {"time": 1_788_307_200 + (index * 86_400), "close": 100 + index}
            for index in range(21)
        ]


def test_market_evidence_collector_turns_supported_watchlist_bars_into_live_evidence():
    from app.services.smart_insights.market_evidence import WatchlistMarketEvidenceCollector

    collector = WatchlistMarketEvidenceCollector(
        kline_service=_KlineService(),
        instruments_loader=lambda: [
            {"market": "Crypto", "symbol": "LINK/USDT"},
            {"market": "VNStock", "symbol": "HPG"},
            {"market": "Forex", "symbol": "XAUUSD"},
        ],
        clock=lambda: AS_OF,
    )

    rows = collector.collect()

    assert len(rows) == 9
    assert {(row.market, row.symbol) for row in rows} == {
        ("crypto", "LINK"),
        ("vn", "HPG"),
        ("gold", "XAU"),
    }
    assert {row.value["metric"] for row in rows} == {
        "market.price.close",
        "market.return_1d_pct",
        "market.return_20d_pct",
    }
    assert all(row.source_code == "datavest-market-bars" for row in rows)
    assert all(row.data_class.value == "LIVE" for row in rows)
    assert all(row.observed_at == AS_OF for row in rows)
    assert all(row.value["evidenceOnly"] is True for row in rows)
