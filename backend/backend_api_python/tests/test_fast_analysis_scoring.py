from app.services.fast_analysis import FastAnalysisService
from app.services import fast_analysis


def _service():
    svc = FastAnalysisService()
    svc._get_ai_calibration = lambda market="Crypto": {}
    return svc


def test_oversold_only_does_not_expand_to_full_bullish_score():
    svc = _service()

    score = svc._calculate_technical_score(
        {"rsi": {"value": 23.0}},
        {"price": 100.0, "changePercent": 0.0},
    )

    assert 0 < score < 20


def test_bearish_breakdown_suppresses_oversold_buy_bias():
    svc = _service()
    indicators = {
        "rsi": {"value": 23.0},
        "macd": {"signal": "bearish"},
        "moving_averages": {"trend": "strong_downtrend"},
        "price_position": 9.2,
        "volume_ratio": 0.58,
        "bollinger": {
            "BB_upper": 81676.6,
            "BB_lower": 68373.55,
        },
        "current_price": 66909.99,
        "volatility": {"pct": 3.23},
    }
    price = {"price": 66909.99, "changePercent": -5.21}

    risk = svc._technical_risk_context(indicators, price)
    score = svc._calculate_technical_score(indicators, price)

    assert risk["panic_breakdown"] is True
    assert score <= -20


def test_input_provenance_is_safe_and_records_the_analysis_snapshot():
    svc = _service()

    provenance = svc._build_input_provenance(
        {
            "price": {"price": 101.25, "source": "binance"},
            "kline": [{"close_time": "2026-09-04T08:00:00Z", "close": 101.25}],
            "_meta": {"success_items": ["price", "kline", "indicators", "crypto_factors"]},
        },
        timeframe="1H",
        captured_at="2026-09-04T08:05:00Z",
    )

    assert provenance["captured_at"] == "2026-09-04T08:05:00Z"
    assert provenance["price_source"] == "binance"
    assert provenance["kline_at"] == "2026-09-04T08:00:00Z"
    assert provenance["components"] == ["price", "technical", "crypto_market_structure"]
    assert len(provenance["checksum"]) == 64
    assert "price" not in provenance


def test_hose_missing_components_are_null_not_neutral_fifty():
    svc = _service()
    score = svc._calculate_objective_score({
        "market": "VNStock", "indicators": {}, "fundamental": {}, "news": [],
        "macro": {}, "price": {},
    }, 0)

    assert score["technical_score"] is None
    assert score["fundamental_score"] is None
    assert score["sentiment_score"] is None
    assert score["overall_score"] is None


def test_hose_technical_only_does_not_dilute_score_with_missing_fundamentals():
    svc = _service()
    score = svc._calculate_objective_score({
        "market": "VNStock", "indicators": {"rsi": {"value": 23.0}},
        "fundamental": {}, "news": [], "macro": {}, "price": {"price": 120000},
    }, 120000)

    assert score["technical_score"] is not None
    assert score["overall_score"] == score["technical_score"]
    assert score["fundamental_score"] is None
    assert score["sentiment_score"] is None


def test_hose_price_only_returns_insufficient_data_not_hold():
    svc = _service()
    result = svc._build_hose_fast_result(
        {"market": "VNStock", "symbol": "FPT", "language": "vi-VN", "model": "test", "timeframe": "1D"},
        {"market": "VNStock", "price": {"price": 120000, "source": "vndirect"},
         "indicators": {}, "fundamental": {}, "news": [], "macro": {}},
        start_time=0, user_id=None, persist_history=False,
    )
    assert result["decision"] == "INSUFFICIENT_DATA"
    assert result["confidence"] is None
    assert result["scores"] == {"technical": None, "fundamental": None, "sentiment": None, "overall": None}
    assert result["score_coverage"]["partial"] is True


def test_hose_fast_analysis_uses_llm_for_supported_narrative_only():
    svc = _service()
    calls = []
    svc.llm_service = type("LLM", (), {
        "safe_call_llm": lambda self, system, user, **kwargs: calls.append((system, user)) or {
            "technical": "RSI cho thấy trạng thái quá bán.",
            "summary": "Model tried to replace verdict",
            "decision": "BUY",
            "fundamental": "Invented revenue",
        }
    })()
    result = svc._build_hose_fast_result(
        {"market": "VNStock", "symbol": "FPT", "language": "vi-VN", "model": "test", "timeframe": "1D"},
        {"market": "VNStock", "price": {"price": 120000, "source": "vndirect"},
         "indicators": {"rsi": {"value": 23.0}}, "fundamental": {}, "news": [], "macro": {}},
        start_time=0, user_id=None, persist_history=False,
    )

    assert calls and "HOSE" in calls[0][0]
    assert result["detailed_analysis"]["technical"] == "RSI cho thấy trạng thái quá bán."
    assert result["detailed_analysis"]["fundamental"] == ""
    assert result["summary"] != "Model tried to replace verdict"


def test_hose_analyze_routes_around_legacy_neutral_consensus(monkeypatch):
    svc = _service()
    monkeypatch.setattr(fast_analysis, "validate_hose_ai_target", lambda market, symbol: symbol)
    svc._collect_market_data = lambda *args, **kwargs: {"market": "VNStock", "price": {}, "indicators": {}}
    result = svc.analyze("VNStock", "FPT", model="test", persist_history=False)

    assert result["decision"] == "INSUFFICIENT_DATA"
    assert result["scores"]["overall"] is None
    assert result["error"] is None

