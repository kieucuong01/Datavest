from app.services.portfolio.positions import enrich_positions_with_prices, summarize_position_rows


def position(market="Crypto", symbol="BTC/USDT", **values):
    return {"market": market, "symbol": symbol, "side": "long", "quantity": 1, "entry_price": 80_000, **values}


def test_missing_price_is_unavailable_not_a_total_loss():
    row = position()
    enrich_positions_with_prices([row], {})
    assert row["current_price"] is None
    assert row["pnl"] is None
    assert row["valuation_status"] == "UNAVAILABLE"
    result = summarize_position_rows([row], {})
    assert result["total_market_value"] is None
    assert result["total_pnl_percent"] is None
    assert result["valued_position_count"] == 0


def test_native_currencies_are_never_added_without_fx():
    rows = [position(), position("VNStock", "FPT", quantity=100, entry_price=100_000)]
    prices = {"Crypto:BTC/USDT": {"price": 85_000}, "VNStock:FPT": {"price": 110_000}}
    result = summarize_position_rows(rows, prices)
    assert result["total_market_value"] is None
    assert result["market_distribution"] == []
    totals = {group["currency"]: group for group in result["currency_summaries"]}
    assert totals["USDT"]["total_market_value"] == 85_000
    assert totals["VND"]["total_market_value"] == 11_000_000


def test_partial_quotes_do_not_create_misleading_totals():
    rows = [position(), position(symbol="ETH/USDT", entry_price=2000)]
    result = summarize_position_rows(rows, {"Crypto:BTC/USDT": {"price": 85_000}})
    assert result["valuation_status"] == "PARTIAL"
    assert result["total_market_value"] is None
    assert result["currency_summaries"][0]["valued_market_value"] == 85_000
    assert result["valued_position_count"] == 1


def test_stale_quote_preserves_valuation_with_explicit_status_and_source():
    row = position()
    enrich_positions_with_prices([row], {"Crypto:BTC/USDT": {"price": 85_000, "stale": True, "source": "binance", "observedAt": "2026-10-01T00:00:00Z"}})
    assert row["pnl"] == 5000
    assert row["valuation_status"] == "STALE"
    assert row["price_observed_at"] == "2026-10-01T00:00:00Z"
    assert row["quote_currency"] == "USDT"


def test_single_currency_totals_preserve_existing_contract():
    result = summarize_position_rows([position()], {"Crypto:BTC/USDT": {"price": 85_000}})
    assert result["total_pnl"] == 5000
    assert result["total_pnl_percent"] == 6.25
    assert result["currency"] == "USDT"


def test_monitor_summaries_do_not_add_native_currencies():
    from app.services.portfolio_monitor import _build_telegram_report
    rows = [position(current_price=85_000, pnl=5000), position("VNStock", "FPT", quantity=100, entry_price=100_000, current_price=110_000, pnl=1_000_000)]
    report = _build_telegram_report(rows, rows, "en-US")
    assert "USDT" in report and "VND" in report
    assert "$10,080,000" not in report


def test_html_report_does_not_turn_missing_price_into_a_loss():
    from app.services.portfolio_monitor import _build_html_report
    rows = [position(current_price=None)]
    report = _build_html_report(rows, rows, "en-US")
    assert "— USDT" in report
    assert "-100.0%" not in report
