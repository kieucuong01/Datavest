"""Shared PDF HTTP-delivery contract tests."""


def test_trading_agents_pdf_delivery_sanitizes_filename_and_disables_caching():
    from app.services.pdf_delivery import trading_agents_pdf_response

    response = trading_agents_pdf_response(
        b"%PDF-1.4 test",
        symbol="BTC/USDT <> test",
        analysis_date="2026-09-05T12:30:00Z",
        summary=True,
    )

    assert response.mimetype == "application/pdf"
    assert "DataVest_TradingAgents_Summary_BTC_USDT_test_20260905.pdf" in response.headers["Content-Disposition"]
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Content-Length"] == str(len(b"%PDF-1.4 test"))
