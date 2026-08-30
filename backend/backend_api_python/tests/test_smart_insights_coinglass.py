from datetime import datetime, timezone

from app.services.smart_insights.coinglass import (
    CoinGlassMarginCollector,
    CoinGlassMaxPainCollector,
)
from app.services.smart_insights.transport import HttpResponse


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


class FakeTransport:
    def __init__(self, body: str):
        self.body = body.encode()

    def fetch(self, url, *, timeout_seconds, max_bytes, headers=None):
        return HttpResponse(status=200, url=url, body=self.body)


def test_margin_collector_ports_legacy_html_contract():
    html = """
    <table><tr><th>Time</th><th>Annualized Interest Rate</th><th>Daily Interest Rate</th><th>Hourly Interest Rate</th></tr>
    <tr><td>2026-08-26 08:00</td><td>4.05%</td><td>0.011%</td><td>0.0005%</td></tr></table>
    """

    rows = CoinGlassMarginCollector(transport=FakeTransport(html)).collect(NOW)

    assert len(rows) == 3
    assert {row.value["metric"] for row in rows} == {
        "crypto.derivatives.margin_borrow.annualized_rate",
        "crypto.derivatives.margin_borrow.daily_rate",
        "crypto.derivatives.margin_borrow.hourly_rate",
    }
    assert rows[0].source_code == "coinglass-margin-borrow"


def test_max_pain_collector_ports_legacy_html_contract():
    html = """
    <table><tr><th></th><th>Ranking</th><th>Symbol</th><th>Price</th><th>Short Max Pain</th><th>Short Distance</th><th>Long Max Pain</th><th>Long Distance</th></tr>
    <tr><td></td><td>1</td><td>BTC</td><td>$100,000</td><td>$99,000 $98,000 -$1,000 -1.00%</td><td>$101,000 $102,000 $1,000 1.00%</td></tr></table>
    """

    rows = CoinGlassMaxPainCollector(transport=FakeTransport(html)).collect(NOW)

    assert len(rows) == 7
    assert all(row.symbol == "BTC" for row in rows)
    assert {row.value["metric"] for row in rows} == {
        "crypto.derivatives.liquidation.current_price_usd",
        "crypto.derivatives.liquidation.short_max_pain_price_usd",
        "crypto.derivatives.liquidation.short_distance_ratio",
        "crypto.derivatives.liquidation.short_max_pain_level_usd",
        "crypto.derivatives.liquidation.long_max_pain_price_usd",
        "crypto.derivatives.liquidation.long_distance_ratio",
        "crypto.derivatives.liquidation.long_max_pain_level_usd",
    }
