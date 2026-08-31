from __future__ import annotations

from datetime import datetime, timezone


NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def test_legacy_dynamic_crypto_sources_are_runtime_collectors() -> None:
    from app.services.smart_insights.collectors import default_collector_registry
    from app.services.smart_insights.sources import source_for_code

    registry = default_collector_registry()
    expected = {
        "bitinfocharts-top-addresses",
        "coinglass-liquidation-maxpain",
        "coinglass-margin-borrow",
        "coinshares-weekly",
    }

    assert expected <= set(registry)
    assert all(source_for_code(code).activation_mode == "RUNTIME" for code in expected)


def test_dynamic_crypto_sources_are_in_the_default_refresh_schedule() -> None:
    from app.services.smart_insights.sources import production_source_codes

    expected = {
        "bitinfocharts-top-addresses",
        "coinglass-liquidation-maxpain",
        "coinglass-margin-borrow",
        "coinshares-weekly",
    }

    assert expected <= set(production_source_codes())


def test_bitinfocharts_browser_collector_normalizes_the_top_100_table() -> None:
    from app.services.smart_insights.bitinfocharts_browser import BitInfoChartsBrowserCollector
    from app.services.smart_insights.legacy_browser import BrowserDocument
    from app.services.smart_insights.sources import source_for_code

    rows = []
    for rank in range(1, 101):
        address = f"bc1q{'%030d' % rank}"
        label = " wallet: Binance-coldwallet Balance:" if rank == 1 else ""
        rows.append(
            f"<tr><td>{rank}</td><td><a href='/bitcoin/address/{address}'>{address}</a>{label}</td>"
            f"<td>1,500 BTC</td><td>2020-01-01</td><td>2026-08-26</td></tr>"
        )
    html = (
        "<table><tr><th>#</th><th>Address</th><th>Balance</th><th>First In</th><th>Last In</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    detail_html = """
        <main>
          <p>Balance: 1,500 BTC</p>
          <p>Received: 2,000 BTC (12 ins) first: 2020-01-01 last: 2026-08-25</p>
          <p>Sent: 500 BTC (3 outs) first: 2020-01-02 last: 2026-08-24</p>
          <p>Unspent outputs: 7</p>
        </main>
    """

    class FakeBrowser:
        def fetch(self, source, url, *, ready):
            assert source.code == "bitinfocharts-top-addresses"
            page = html if url.endswith("top-100-richest-bitcoin-addresses.html") else detail_html
            assert ready(page)
            return BrowserDocument(html=page, final_url=url, observed_at=NOW)

    observations = BitInfoChartsBrowserCollector(browser=FakeBrowser()).collect(NOW)

    assert observations[0].warnings == ("HEURISTIC_ADDRESS_COHORT",)
    assert any(row.value["metric"] == "crypto.large_address.excluded_balance_btc" for row in observations)
    detail_rows = [row for row in observations if row.value["metric"] == "crypto.large_address.address_received_total_btc"]
    assert len(detail_rows) == 12
    assert detail_rows[0].value["value"] == "2000"
    assert detail_rows[0].value["dimensions"]["detail_scope"] == "top12_non_excluded"
    assert any(row.value["metric"] == "crypto.large_address.address_last_activity_age_days" for row in observations)


def test_coinshares_ocr_reconstruction_keeps_the_old_table_contract() -> None:
    from app.services.smart_insights.coinshares_browser import OcrToken, reconstruct_table

    def token(text: str, x: int, y: int) -> OcrToken:
        return OcrToken(text=text, confidence=0.98, box=(x, y, x + 40, y + 12))

    tokens = [
        token("Data available as at 24 August 2026", 0, 10),
        token("Asset", 10, 100),
        token("Week Flow", 100, 100),
        token("AUM", 200, 100),
        token("US$m", 300, 10),
        token("Bitcoin", 10, 130),
        token("100", 100, 130),
        token("1,000", 200, 130),
        token("Ethereum", 10, 160),
        token("-50", 100, 160),
        token("500", 200, 160),
    ]

    table = reconstruct_table(tokens, dimension="asset")

    assert table.effective_at == datetime(2026, 8, 24, tzinfo=timezone.utc)
    assert [row.label for row in table.rows] == ["Bitcoin", "Ethereum"]
    assert table.rows[0].week_flow_usd == 100_000_000
