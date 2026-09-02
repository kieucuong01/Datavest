from app.services.ai_assistant_insights import (
    build_daily_brief,
    select_watchlist_reports_for_date,
)


def test_select_watchlist_reports_uses_exact_date_and_never_falls_back():
    watchlist = [
        {"market": "Crypto", "symbol": "BTC/USDT"},
        {"market": "Forex", "symbol": "XAUUSD"},
    ]
    reports = [
        {
            "id": 1,
            "market": "Crypto",
            "symbol": "BTC/USDT",
            "created_at": "2026-09-01T08:00:00+00:00",
            "status": "completed",
            "decision": "BUY",
            "confidence": 72,
            "summary": "Older BTC report",
        },
        {
            "id": 2,
            "market": "Crypto",
            "symbol": "BTC/USDT",
            "created_at": "2026-09-02T07:00:00+00:00",
            "status": "completed",
            "decision": "HOLD",
            "confidence": 61,
            "summary": "Current BTC report",
        },
        {
            "id": 3,
            "market": "Crypto",
            "symbol": "BTC/USDT",
            "created_at": "2026-09-02T09:00:00+00:00",
            "status": "completed",
            "decision": "SELL",
            "confidence": 65,
            "summary": "Newest current BTC report",
        },
    ]

    selected = select_watchlist_reports_for_date(watchlist, reports, "2026-09-02")

    assert selected["crypto:BTC"]["id"] == 3
    assert selected["gold:XAU"] is None


def test_daily_brief_only_summarizes_reports_from_selected_day():
    reports = [
        {
            "id": 3,
            "market": "Crypto",
            "symbol": "BTC/USDT",
            "created_at": "2026-09-02T09:00:00+00:00",
            "status": "completed",
            "decision": "SELL",
            "confidence": 65,
            "summary": "BTC biến động mạnh, cần theo dõi thanh khoản.",
        },
        {
            "id": 4,
            "market": "VNStock",
            "symbol": "VNINDEX",
            "created_at": "2026-09-02T10:00:00+00:00",
            "status": "completed",
            "decision": "HOLD",
            "confidence": 58,
            "summary": "VNINDEX chờ tín hiệu xác nhận mới.",
        },
    ]

    brief = build_daily_brief(reports, "2026-09-02", "vi-VN")

    assert brief["status"] == "AVAILABLE"
    assert brief["assetCount"] == 2
    assert brief["sourceAnalysisIds"] == [3, 4]
    assert "BTC" in brief["content"]
    assert "VNINDEX" in brief["content"]
    assert len(brief["content"].split()) <= 650
