"""Public guest-report publishing stays separate from account-owned history."""

from __future__ import annotations

from datetime import date


def test_public_reports_expose_crypto_assets_only_for_the_guest_research_set():
    from app.services.smart_insights.public_reports import (
        PUBLIC_GUEST_ASSET_SCOPE,
        PUBLIC_RESEARCH_ASSET_SCOPE,
    )

    assert [asset["displaySymbol"] for asset in PUBLIC_GUEST_ASSET_SCOPE] == ["BTC", "SOL", "LINK", "XAU"]
    assert [asset["displaySymbol"] for asset in PUBLIC_RESEARCH_ASSET_SCOPE] == ["BTC", "SOL", "LINK", "XAU"]


def test_initial_public_deep_reports_can_be_queued_for_only_the_new_crypto_assets():
    from app.services.smart_insights.public_research_publisher import PublicResearchPublisher

    class TradingRepository:
        def __init__(self):
            self.calls = []

        def create_run(self, **kwargs):
            self.calls.append(kwargs)

    class Queue:
        def __init__(self):
            self.calls = []

        def __call__(self, run_id):
            self.calls.append(run_id)

    reports = _Reports()
    repository = TradingRepository()
    queue = Queue()
    publisher = PublicResearchPublisher(
        reports=reports,
        trading_repository=repository,
        enqueue_trading_run=queue,
        system_user_id=lambda: 42,
    )

    result = publisher.enqueue_initial_deep_reports(
        asset_keys=("crypto:SOL/USDT", "crypto:LINK/USDT"),
        effective_date=date(2026, 9, 14),
    )

    assert result == {"queued": 2, "failed": 0}
    assert [call["request"]["symbol"] for call in repository.calls] == ["SOL/USDT", "LINK/USDT"]
    assert len(queue.calls) == 2
    assert [row["asset_key"] for row in reports.pending] == [
        "crypto:SOL/USDT",
        "crypto:LINK/USDT",
    ]


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

    assert result == {"published": 4, "failed": 0}
    assert [call["market"] for call in analysis.calls] == ["Crypto", "Crypto", "Crypto", "Forex"]
    assert [call["symbol"] for call in analysis.calls] == ["BTC/USDT", "SOL/USDT", "LINK/USDT", "XAUUSD"]
    assert all(call["language"] == "vi-VN" for call in analysis.calls)
    assert all(call["persist_history"] is False for call in analysis.calls)
    assert all(call.get("user_id") is None for call in analysis.calls)
    assert [row["asset_key"] for row in reports.completed] == [
        "crypto:BTC/USDT",
        "crypto:SOL/USDT",
        "crypto:LINK/USDT",
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
