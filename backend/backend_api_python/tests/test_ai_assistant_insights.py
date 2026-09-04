from app.services.ai_assistant_insights import (
    AiAssistantInsightsService,
    build_daily_brief,
    select_watchlist_reports_for_date,
)
from datetime import datetime, timezone


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


def test_daily_brief_exposes_at_most_five_actionable_asset_highlights():
    reports = [
        {
            "id": index,
            "market": "Crypto",
            "symbol": f"TOKEN{index}/USDT",
            "created_at": f"2026-09-02T{index:02d}:00:00+00:00",
            "status": "completed",
            "decision": decision,
            "confidence": confidence,
            "summary": f"Tín hiệu cần theo dõi cho TOKEN{index}.",
        }
        for index, (decision, confidence) in enumerate(
            [("HOLD", 99), ("BUY", 61), ("SELL", 85), ("BUY", 72), ("HOLD", 98), ("SELL", 67), ("HOLD", 97)],
            start=1,
        )
    ]

    brief = build_daily_brief(reports, "2026-09-02", "vi-VN")

    assert len(brief["highlights"]) == 5
    assert all({"assetKey", "market", "symbol", "displaySymbol", "decision", "summary", "sourceAnalysisId"} <= set(item) for item in brief["highlights"])
    assert [item["decision"] for item in brief["highlights"][:4]] == ["SELL", "BUY", "SELL", "BUY"]
    assert brief["highlights"][0]["assetKey"] == "crypto:TOKEN3"


def test_public_report_keeps_the_detail_needed_by_smart_insights_modal():
    report = {
        "id": 9,
        "market": "Crypto",
        "symbol": "BTC/USDT",
        "created_at": "2026-09-02T09:00:00+00:00",
        "decision": "SELL",
        "confidence": 62,
        "summary": "BTC cần thận trọng.",
        "reasons": ["RSI cao"],
        "scores": {"technical": 45},
        "full_result": {
            "model": "deepseek-chat",
            "language": "vi-VN",
            "timeframe": "1D",
            "detailed_analysis": {
                "technical": "MACD suy yếu.",
                "fundamental": "Dòng tiền phái sinh thận trọng.",
                "sentiment": "Tâm lý thị trường yếu hơn.",
            },
            "trading_plan": {"entry_price": 100, "stop_loss": 95, "take_profit": 110},
            "risks": ["Biến động cao"],
            "market_data": {"current_price": 101, "change_24h": -2.5},
            "indicators": {"rsi": {"value": 63.49}},
            "crypto_factors": {"funding_rate": 0.01, "open_interest": 1000},
            "crypto_factor_score": -18,
            "crypto_factor_breakdown": [{"factor": "funding_oi", "score": -18}],
            "crypto_factor_summary": "Đòn bẩy có dấu hiệu thận trọng.",
            "consensus": {"consensus_decision": "SELL", "agreement_ratio": 0.75},
            "trend_outlook": {"next_24h": {"trend": "SELL", "score": -20}},
            "trend_outlook_summary": "Ngắn hạn nghiêng về giảm.",
            "analysis_time_ms": 1200,
        },
    }

    public_report = AiAssistantInsightsService._public_report(report)

    assert public_report["detailedAnalysis"]["technical"] == "MACD suy yếu."
    assert public_report["tradingPlan"]["entry_price"] == 100
    assert public_report["risks"] == ["Biến động cao"]
    assert public_report["marketData"]["current_price"] == 101
    assert public_report["indicators"]["rsi"]["value"] == 63.49
    assert public_report["cryptoFactors"]["funding_rate"] == 0.01
    assert public_report["cryptoFactorBreakdown"][0]["factor"] == "funding_oi"
    assert public_report["consensus"]["agreement_ratio"] == 0.75
    assert public_report["trendOutlook"]["next_24h"]["trend"] == "SELL"
    assert public_report["timeframe"] == "1D"
    assert public_report["model"] == "deepseek-chat"
    assert "raw_result" not in public_report


def test_overview_marks_a_missing_report_from_the_matching_monitor_state():
    today = "2026-09-04"
    now = datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)
    watchlist = [
        {"market": "Crypto", "symbol": "BTC/USDT"},
        {"market": "Forex", "symbol": "XAUUSD"},
    ]
    reports = [{
        "id": 10,
        "market": "Crypto",
        "symbol": "BTC/USDT",
        "created_at": "2026-09-04T08:45:00+00:00",
        "status": "completed",
        "decision": "BUY",
        "confidence": 71,
        "summary": "BTC report",
        "full_result": {
            "input_data": {
                "captured_at": "2026-09-04T08:42:00+00:00",
                "price_source": "binance",
                "timeframe": "1H",
                "checksum": "input-checksum",
                "components": ["price", "technical"],
            },
        },
    }]
    monitors = [
        {
            "id": 1,
            "config": {"market": "Crypto", "symbol": "BTC/USDT", "run_interval_minutes": 60},
            "is_active": True,
            "last_run_at": "2026-09-04T08:45:00+00:00",
            "next_run_at": "2026-09-04T09:45:00+00:00",
            "last_result": {"success": True},
            "run_count": 3,
        },
        {
            "id": 2,
            "config": {"market": "Forex", "symbol": "XAUUSD", "run_interval_minutes": 60},
            "is_active": False,
            "last_run_at": "2026-09-03T08:45:00+00:00",
            "next_run_at": "2026-09-03T09:45:00+00:00",
            "last_result": {},
            "run_count": 1,
        },
    ]

    service = AiAssistantInsightsService(
        memory=type("Memory", (), {"list_reports_for_user": lambda *_args, **_kwargs: reports})(),
        watchlist_loader=lambda _user_id: watchlist,
        monitor_loader=lambda _user_id: monitors,
        now_loader=lambda: now,
    )

    overview = service.get_overview(user_id=7, as_of=today)
    btc, xau = overview["opinions"]

    assert btc["analysisStatus"] == "AVAILABLE"
    assert btc["dataFreshness"] == "FRESH"
    assert btc["monitor"]["state"] == "SCHEDULED"
    assert btc["report"]["inputData"] == {
        "capturedAt": "2026-09-04T08:42:00Z",
        "priceSource": "binance",
        "timeframe": "1H",
        "klineAt": None,
        "checksum": "input-checksum",
        "components": ["price", "technical"],
    }
    assert xau["report"] is None
    assert xau["analysisStatus"] == "PAUSED"
    assert xau["monitor"]["state"] == "PAUSED"


def test_overview_and_daily_brief_expose_date_and_data_readiness_contract():
    today = "2026-09-04"
    now = datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)
    watchlist = [{"market": "Crypto", "symbol": "BTC/USDT"}]
    reports = [{
        "id": 12,
        "market": "Crypto",
        "symbol": "BTC/USDT",
        "created_at": "2026-09-04T08:45:00+00:00",
        "status": "completed",
        "decision": "HOLD",
        "confidence": 60,
        "summary": "BTC đang chờ xác nhận.",
        "full_result": {"input_data": {"captured_at": "2026-09-04T08:42:00+00:00"}},
    }]

    service = AiAssistantInsightsService(
        memory=type("Memory", (), {"list_reports_for_user": lambda *_args, **_kwargs: reports})(),
        watchlist_loader=lambda _user_id: watchlist,
        monitor_loader=lambda _user_id: [],
        now_loader=lambda: now,
    )

    overview = service.get_overview(user_id=7, as_of=today)

    assert overview["requestedAsOf"] == today
    assert overview["resolvedAsOf"] == today
    assert overview["fetchedAt"].endswith("+07:00")
    assert overview["freshness"] == "FRESH"
    assert overview["coverage"] == {"expectedAssets": 1, "availableAssets": 1, "ratio": 1.0}
    assert overview["dailyBrief"]["requestedAsOf"] == today
    assert overview["dailyBrief"]["resolvedAsOf"] == today
    assert overview["dailyBrief"]["coverage"]["expectedAssets"] == 1


def test_public_report_keeps_only_safe_input_provenance_fields():
    report = {
        "id": 11,
        "market": "Crypto",
        "symbol": "ETH/USDT",
        "created_at": "2026-09-04T08:00:00+00:00",
        "full_result": {
            "input_data": {
                "captured_at": "2026-09-04T07:59:00+00:00",
                "price_source": "exchange_quote",
                "timeframe": "1H",
                "kline_at": "2026-09-04T07:00:00+00:00",
                "checksum": "abc123",
                "components": ["price", "technical", "crypto_market_structure"],
                "provider_api_key": "must-not-leak",
            },
        },
    }

    public_report = AiAssistantInsightsService._public_report(report)

    assert public_report["inputData"]["checksum"] == "abc123"
    assert public_report["inputData"]["components"] == ["price", "technical", "crypto_market_structure"]
    assert "provider_api_key" not in public_report["inputData"]
