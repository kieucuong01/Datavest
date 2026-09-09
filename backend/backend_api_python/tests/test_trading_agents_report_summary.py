from app.services.trading_agents_report_summary import build_report_summary


def test_llm_summary_is_bounded_and_uses_only_known_report_sections() -> None:
    report = """# BTC report

## I. Market analysis
Price momentum improved after stronger volume.

## V. Portfolio decision
**Recommendation**: HOLD
"""

    summary = build_report_summary(
        report=report,
        language="en-US",
        call_llm=lambda _messages: '''{
          "overview": "Momentum improved while volume strengthened.",
          "conclusion": "HOLD",
          "key_points": ["Watch liquidity confirmation."],
          "sections": [{"title": "Market analysis", "summary": "Price momentum improved after stronger volume."}]
        }''',
    )

    assert summary["overview"] == "Momentum improved while volume strengthened."
    assert summary["conclusion"] == "HOLD"
    assert summary["sections"] == [{"title": "Market analysis", "summary": "Price momentum improved after stronger volume."}]
