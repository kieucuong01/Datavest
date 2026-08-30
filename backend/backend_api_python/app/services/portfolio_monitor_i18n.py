"""Localized text helpers for portfolio monitor alerts."""

from __future__ import annotations

from typing import Any, Dict

ALERT_MESSAGES: Dict[str, Dict[str, str]] = {
    "zh-CN": {
        "price_above": "价格突破预警：{symbol} 当前价格 ${current_price:.4f} 已高于 ${threshold:.4f}",
        "price_below": "价格跌破预警：{symbol} 当前价格 ${current_price:.4f} 已低于 ${threshold:.4f}",
        "pnl_above": "盈利预警：{symbol} 当前盈亏 {pnl_percent:.1f}% 已达到 {threshold:.1f}% 目标",
        "pnl_below": "亏损预警：{symbol} 当前盈亏 {pnl_percent:.1f}% 已触发 {threshold:.1f}% 止损线",
        "alert_title": "价格/盈亏预警",
    },
    "en-US": {
        "price_above": "Price alert: {symbol} current price ${current_price:.4f} has exceeded ${threshold:.4f}",
        "price_below": "Price alert: {symbol} current price ${current_price:.4f} has dropped below ${threshold:.4f}",
        "pnl_above": "Profit alert: {symbol} P&L {pnl_percent:.1f}% has reached {threshold:.1f}% target",
        "pnl_below": "Loss alert: {symbol} P&L {pnl_percent:.1f}% has hit {threshold:.1f}% stop-loss",
        "alert_title": "Price/P&L Alert",
    },
    "vi-VN": {
        "price_above": "Cảnh báo giá: {symbol} có giá hiện tại ${current_price:.4f}, đã vượt ${threshold:.4f}",
        "price_below": "Cảnh báo giá: {symbol} có giá hiện tại ${current_price:.4f}, đã giảm dưới ${threshold:.4f}",
        "pnl_above": "Cảnh báo lợi nhuận: {symbol} đang lãi/lỗ {pnl_percent:.1f}%, đã đạt mục tiêu {threshold:.1f}%",
        "pnl_below": "Cảnh báo thua lỗ: {symbol} đang lãi/lỗ {pnl_percent:.1f}%, đã chạm ngưỡng cắt lỗ {threshold:.1f}%",
        "alert_title": "Cảnh báo giá/lãi lỗ",
    },
}


def normalize_language(language: str = "en-US") -> str:
    from app.utils.language import normalize_product_language

    return normalize_product_language(language)


def get_alert_message(alert_type: str, language: str = "en-US", **kwargs: Any) -> str:
    """Return a localized alert message."""
    lang = normalize_language(language)
    template = ALERT_MESSAGES.get(lang, ALERT_MESSAGES["en-US"]).get(alert_type, "")
    return template.format(**kwargs) if template else ""


def get_alert_title(language: str = "en-US") -> str:
    """Return a localized alert title."""
    lang = normalize_language(language)
    return ALERT_MESSAGES.get(lang, ALERT_MESSAGES["en-US"]).get("alert_title", "Alert")
