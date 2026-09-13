"""Public guest-report publishing stays separate from account-owned history."""

from __future__ import annotations

from datetime import date


def test_public_reports_keep_vnindex_visible_to_guests_but_do_not_schedule_it_for_research():
    from app.services.smart_insights.public_reports import (
        PUBLIC_GUEST_ASSET_SCOPE,
        PUBLIC_RESEARCH_ASSET_SCOPE,
    )

    assert [asset["displaySymbol"] for asset in PUBLIC_GUEST_ASSET_SCOPE] == ["BTC", "VNINDEX", "XAU"]
    assert [asset["displaySymbol"] for asset in PUBLIC_RESEARCH_ASSET_SCOPE] == ["BTC", "XAU"]


class _Reports:
    def __init__(self):
        self.pending = []
        self.completed = []
        self.failed = []

    def mark_pending(self, **kwargs):
        self.pending.append(kwargs)

    def mark_complete(self, **kwargs):
        self.completed.append(kwargs)

    def mark_failed(self, **kwargs):
        self.failed.append(kwargs)


class _FastAnalysis:
    def __init__(self):
        self.calls = []

    def analyze(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "summary": f"{kwargs['symbol']} daily summary",
            "decision": "HOLD",
            "confidence": 61,
            "reasons": ["Price action is mixed."],
        }


def test_daily_public_quick_reports_use_only_fixed_assets_without_personal_history():
    from app.services.smart_insights.public_research_publisher import PublicResearchPublisher

    reports = _Reports()
    analysis = _FastAnalysis()
    publisher = PublicResearchPublisher(reports=reports, fast_analysis=analysis)

    result = publisher.publish_daily_quick_reports(effective_date=date(2026, 9, 13))

    assert result == {"published": 2, "failed": 0}
    assert [call["market"] for call in analysis.calls] == ["Crypto", "Forex"]
    assert [call["symbol"] for call in analysis.calls] == ["BTC/USDT", "XAUUSD"]
    assert all(call["language"] == "vi-VN" for call in analysis.calls)
    assert all(call["persist_history"] is False for call in analysis.calls)
    assert all(call.get("user_id") is None for call in analysis.calls)
    assert [row["asset_key"] for row in reports.completed] == [
        "crypto:BTC/USDT",
        "forex:XAUUSD",
    ]
    assert all("memory_id" not in row["payload"] for row in reports.completed)


def test_public_deep_projection_uses_only_completed_report_and_never_leaks_run_id():
    from app.services.smart_insights.public_research_publisher import PublicResearchPublisher

    reports = _Reports()
    publisher = PublicResearchPublisher(reports=reports)

    payload = publisher.build_deep_payload(
        display_symbol="BTC",
        report_markdown="# BTC\nPrivate run id: internal-run-123\n\x00",
    )

    assert payload["title"] == "Phân tích chuyên sâu BTC"
    assert payload["body"] == "# BTC\n"
    assert "internal-run-123" not in payload["body"]
    assert "run_id" not in payload
    assert "sourceRunId" not in payload
    assert payload["provenance"] == {"engine": "TradingAgents", "schedule": "weekly"}
