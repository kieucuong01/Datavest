from app.routes.ai_chat import _build_system_prompt
from app.routes.indicator import _indicator_ai_text, _indicator_hint_to_text, _indicator_human_summary
from app.services.ai_skill_registry import list_skills
from app.services.ai_tool_registry import list_tools
from app.services.strategy_review import StrategyReviewService
from app.services.fast_analysis import FastAnalysisService
from app.data_providers.economic_calendar import _build_ai_calendar_insight
from app.services.fast_analysis_formatters import build_trend_outlook_summary
from app.services.portfolio_monitor_i18n import get_alert_message, get_alert_title
from app.utils.language import (
    language_instruction,
    normalize_product_language,
)


def test_product_language_normalizes_vietnamese_variants_and_retires_chinese():
    assert normalize_product_language("vi") == "vi-VN"
    assert normalize_product_language("vi_VN") == "vi-VN"
    assert normalize_product_language("en") == "en-US"
    assert normalize_product_language("zh-CN") == "en-US"


def test_vietnamese_instruction_forbids_english_and_chinese_prose():
    instruction = language_instruction("vi-VN")

    assert "tiếng Việt" in instruction
    assert "đầy đủ dấu" in instruction
    assert "tiếng Anh" in instruction
    assert "tiếng Trung" in instruction


def test_copilot_system_prompt_enforces_vietnamese_for_every_visible_field():
    prompt = _build_system_prompt("vi-VN", {}, "general", False)

    assert "toàn bộ nội dung người dùng nhìn thấy" in prompt
    assert "tiếng Việt" in prompt


def test_fast_analysis_prompt_enforces_vietnamese_structured_fields():
    service = FastAnalysisService()
    system_prompt, _ = service._build_analysis_prompt(
        {"market": "Crypto", "symbol": "BTC/USDT", "price": {"price": 100, "changePercent": 1}},
        "vi-VN",
    )

    assert "tiếng Việt" in system_prompt
    assert "summary, key_reasons, risks" in system_prompt


def test_portfolio_alerts_are_vietnamese_when_ui_is_vietnamese():
    assert get_alert_title("vi-VN") == "Cảnh báo giá/lãi lỗ"
    message = get_alert_message(
        "price_above",
        "vi-VN",
        symbol="BTC/USDT",
        current_price=100.0,
        threshold=90.0,
    )
    assert message.startswith("Cảnh báo giá:")
    assert "đã vượt" in message


def test_builtin_ai_skills_expose_vietnamese_public_copy():
    skills = {item["id"]: item for item in list_skills("vi-VN", include_disabled=True)}

    assert skills["market_diagnosis"]["label"] == "Chẩn đoán thị trường"
    assert "xu hướng" in skills["market_diagnosis"]["description"].lower()
    assert "Hãy" in skills["market_diagnosis"]["prompt"]


def test_builtin_ai_tools_expose_vietnamese_public_copy():
    tools = {item["id"]: item for item in list_tools("vi-VN")}

    assert tools["market_data.lookup"]["label"] == "Tra cứu dữ liệu thị trường"
    assert "giá" in tools["market_data.lookup"]["description"].lower()
    assert tools["mcp.get_price"]["label"] == "Xem giá mới nhất"


def test_indicator_ai_validation_copy_is_vietnamese():
    assert _indicator_ai_text("prompt_required", "vi-VN") == "Vui lòng nhập yêu cầu cho AI."
    assert "Thiếu" in _indicator_hint_to_text("MISSING_OUTPUT", lang="vi-VN")

    summary = _indicator_human_summary(
        {"hints": []},
        {"hints": []},
        auto_fix_applied=False,
        auto_fix_succeeded=False,
        returned_candidate="initial",
        lang="vi-VN",
    )
    assert summary["title"].startswith("AI đã tạo")
    assert summary["returned_text"] == "Mã trả về là phiên bản được tạo ban đầu."


def test_strategy_review_rule_diagnostics_are_vietnamese():
    diagnostics, recommendations = StrategyReviewService()._build_rule_review(
        metrics={"closed_trades_with_pnl": 0},
        strategy={},
        trading_config={},
        bot_type="",
        language="vi-VN",
    )

    assert diagnostics[0]["title"] == "Mẫu dữ liệu hiện còn ít"
    assert recommendations[0]["title"] == "Tích lũy thêm giao dịch đã đóng"


def test_fast_analysis_deterministic_crypto_copy_is_vietnamese():
    service = FastAnalysisService()
    factor_result = service._calculate_crypto_factor_score(
        {
            "funding_rate": 0.02,
            "open_interest_change_24h": 5,
            "exchange_netflow": -100,
            "signals": {"derivatives_bias": "bullish", "flow_bias": "bullish", "squeeze_risk": "medium"},
        },
        {"changePercent": 2},
        "vi-VN",
    )

    reasons = " ".join(item["reason"] for item in factor_result["breakdown"])
    assert "Funding" not in reasons
    assert "Dữ liệu" not in factor_result["summary"] or "phái sinh" in factor_result["summary"]
    assert "OI" in reasons or "hợp đồng mở" in reasons
    assert "dòng tiền" in reasons.lower()


def test_fast_analysis_outlook_and_validation_copy_are_vietnamese():
    summary = build_trend_outlook_summary(
        {"next_24h": {"trend": "BUY", "strength": "strong"}},
        "vi-VN",
    )
    assert "cường độ mạnh" in summary
    assert "strong" not in summary

    service = FastAnalysisService()
    result = service._validate_and_constrain(
        {"decision": "BUY", "confidence": 80, "summary": "Tóm tắt"},
        100,
        indicators={
            "rsi": {"value": 75},
            "macd": {"signal": "bearish"},
            "moving_averages": {"trend": "downtrend"},
        },
        language="vi-VN",
    )
    assert "technical indicators" not in result["summary"]
    assert "chỉ báo kỹ thuật" in result["summary"]


def test_economic_calendar_ai_insight_has_vietnamese_fields():
    insight = _build_ai_calendar_insight({
        "name": "美国CPI月率",
        "name_en": "US CPI m/m",
        "importance": "high",
        "actual_impact": "bullish",
        "is_released": False,
    })
    assert "title_vi" in insight and "summary_vi" in insight
    assert "tiếng" not in insight["title_vi"]
    assert "偏利" not in insight["title_vi"]
