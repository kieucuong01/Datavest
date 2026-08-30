"""Tests for app.services.ai_bot_symbol_detect.

Detection feeds the AI bot recommender with real K-line data instead of
letting the LLM hallucinate price ranges. Bugs here directly translate to
unusable bot recommendations (the original bug: 'XAU' fell through and the
LLM picked grid bounds out of thin air).
"""
import pytest

from app.services.ai_bot_symbol_detect import detect_market_and_symbol


class TestCryptoDetection:
    @pytest.mark.parametrize("prompt,expected_symbol", [
        ("帮我做一个 BTC 的网格机器人", "BTC/USDT"),
        ("Use ETH for trend following", "ETH/USDT"),
        ("solana DCA 策略", "SOL/USDT"),
        ("ADA grid bot please", "ADA/USDT"),
        ("Set up DOGE martingale", "DOGE/USDT"),
        # Long-form names
        ("ethereum trend bot", "ETH/USDT"),
        ("bitcoin DCA every day", "BTC/USDT"),
    ])
    def test_known_crypto_tickers(self, prompt, expected_symbol):
        result = detect_market_and_symbol(prompt)
        assert result == ("Crypto", expected_symbol), f"prompt={prompt!r}"

    def test_explicit_pair_with_usdt(self):
        # PEPE isn't in the lookup table — regex fallback should still find it.
        result = detect_market_and_symbol("PEPE/USDT pumping, grid bot?")
        assert result is not None
        market, symbol = result
        assert market == "Crypto"
        assert symbol.startswith("PEPE")

    def test_dash_pair_format(self):
        result = detect_market_and_symbol("ARB-USDT range trade")
        assert result is not None
        assert result[0] == "Crypto"


class TestForexDetection:
    """Gold is the only instrument exposed through the Forex namespace."""

    @pytest.mark.parametrize("prompt,expected", [
        ("请根据XAU最近行情走势帮我做网格交易", ("Forex", "XAUUSD")),
        ("trade gold today", ("Forex", "XAUUSD")),
        ("XAU/USD swing trade", ("Forex", "XAUUSD")),
        ("XAUUSD martingale", ("Forex", "XAUUSD")),
    ])
    def test_known_forex_pairs(self, prompt, expected):
        assert detect_market_and_symbol(prompt) == expected

    def test_unknown_forex_pair_via_regex(self):
        # Generic FX is outside the product scope.
        result = detect_market_and_symbol("USD/ZAR carry trade")
        assert result != ("Forex", "USD/ZAR")

    def test_vietnam_stock_is_supported(self):
        assert detect_market_and_symbol("FPT trend strategy") == ("VNStock", "FPT")


class TestUSStockDetection:
    @pytest.mark.parametrize("prompt,expected_symbol", [
        ("TSLA DCA 每周", "TSLA"),
        ("AAPL trend bot", "AAPL"),
        ("Apple stock dca", "AAPL"),
        ("NVDA 趋势策略", "NVDA"),
        ("Nvidia grid bot", "NVDA"),
        ("SPY weekly DCA", "SPY"),
    ])
    def test_known_stock_tickers(self, prompt, expected_symbol):
        result = detect_market_and_symbol(prompt)
        assert result == ("USStock", expected_symbol), f"prompt={prompt!r}"

    def test_unknown_ticker_via_regex(self):
        # PYPL isn't explicitly listed; regex fallback should treat it as stock.
        result = detect_market_and_symbol("PYPL DCA monthly")
        assert result == ("USStock", "PYPL")


class TestPrecedence:
    """Forex must beat the all-caps stop-list / ambiguous tokens."""

    def test_xau_alone_resolves_forex_not_stock(self):
        # 'XAU' is a 3-letter all-caps token that the stock regex would
        # otherwise grab. Forex lookup table runs first.
        assert detect_market_and_symbol("XAU 走势") == ("Forex", "XAUUSD")

    def test_btc_alone_resolves_crypto_not_stock(self):
        # 'BTC' could grammatically match the stock regex; crypto map wins.
        assert detect_market_and_symbol("BTC analysis") == ("Crypto", "BTC/USDT")


class TestNoMatch:
    @pytest.mark.parametrize("prompt", [
        "",
        "   ",
        "我想做一个机器人",
        "set me up with a trend strategy",
        "请帮我推荐一个策略",
    ])
    def test_no_obvious_symbol_returns_none(self, prompt):
        assert detect_market_and_symbol(prompt) is None

    def test_stop_words_do_not_become_tickers(self):
        # 'BUY', 'BOT', 'GRID' are common in user prompts but aren't tickers.
        # Without the stop-list they'd be returned as USStock false positives.
        assert detect_market_and_symbol("set up a grid bot to buy") is None
        assert detect_market_and_symbol("DCA bot please") is None
