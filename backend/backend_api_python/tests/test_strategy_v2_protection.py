import pandas as pd
import pytest

from app.services.strategy_v2 import (
    OrderIntent,
    ProtectionEngine,
    ProtectionSpec,
    ProtectionState,
    StrategyV2BacktestRunner,
)


def _frame(rows):
    index = pd.date_range("2026-01-01", periods=len(rows), freq="4h")
    return pd.DataFrame(rows, index=index, columns=["open", "high", "low", "close", "volume"])


PROTECTED_ENTRY = """
def initialize(context):
    g.symbol = "Crypto:BTC/USDT"
    context.set_universe([g.symbol])
    context.subscribe(frequency="4h")

def handle_data(context, data):
    if get_position(g.symbol).amount == 0:
        order_target_percent(
            g.symbol,
            1.0,
            reason="entry",
            stop_loss_pct=0.02,
            take_profit_pct=0.05,
        )
"""


def test_backtest_protection_fills_at_gap_open():
    frame = _frame([
        (100, 101, 99, 100, 1000),
        (100, 101, 99, 100, 1000),
        (95, 96, 94, 95, 1000),
        (95, 96, 94, 95, 1000),
    ])
    result = StrategyV2BacktestRunner(
        code=PROTECTED_ENTRY,
        frames={"Crypto:BTC/USDT": frame},
        initial_capital=10_000,
        commission=0,
        slippage=0,
    ).run()

    closed = result["closedTrades"][0]
    assert closed["close_reason"] == "stop_loss"
    assert closed["exit_price"] == pytest.approx(95.0)
    assert result["protectionEvents"][0]["triggerPrice"] == pytest.approx(98.0)


def test_backtest_protection_fills_at_stop_inside_bar():
    frame = _frame([
        (100, 101, 99, 100, 1000),
        (100, 101, 99, 100, 1000),
        (100, 101, 97, 99, 1000),
        (99, 100, 98, 99, 1000),
    ])
    result = StrategyV2BacktestRunner(
        code=PROTECTED_ENTRY,
        frames={"Crypto:BTC/USDT": frame},
        initial_capital=10_000,
        commission=0,
        slippage=0,
    ).run()

    assert result["closedTrades"][0]["exit_price"] == pytest.approx(98.0)


def test_backtest_protection_closes_a_single_crypto_lot_without_repeating():
    code = """
def initialize(context):
    g.symbol = "Crypto:BTC/USDT"
    g.sent = False
    context.set_universe([g.symbol])
    context.subscribe(frequency="4h")

def handle_data(context, data):
    if not g.sent:
        order(g.symbol, 0.00000001, reason="entry", stop_loss_pct=0.02)
        g.sent = True
"""
    frame = _frame([
        (1_000_000, 1_010_000, 990_000, 1_000_000, 1000),
        (1_000_000, 1_010_000, 990_000, 1_000_000, 1000),
        (950_000, 960_000, 940_000, 950_000, 1000),
        (950_000, 960_000, 940_000, 950_000, 1000),
    ])
    result = StrategyV2BacktestRunner(
        code=code,
        frames={"Crypto:BTC/USDT": frame},
        initial_capital=10_000,
        commission=0,
        slippage=0,
    ).run()

    assert len(result["protectionEvents"]) == 1
    assert result["protectionEvents"][0]["reason"] == "stop_loss"
    assert result["positions"] == {}
    assert result["totalTrades"] == 1


def test_conservative_intrabar_mode_prioritizes_stop_loss():
    spec = ProtectionSpec(stop_loss_pct=0.02, take_profit_pct=0.05)
    state = ProtectionState.open(
        symbol="Crypto:BTC/USDT@spot",
        side="long",
        entry_price=100,
        spec=spec,
        opened_at="2026-01-01",
    )
    decision = ProtectionEngine().evaluate_bar(
        state,
        timestamp="2026-01-01 04:00:00",
        open_price=100,
        high_price=106,
        low_price=97,
    )

    assert decision is not None
    assert decision.reason == "stop_loss"
    assert decision.price == pytest.approx(98.0)


def test_scale_in_preserves_an_activated_trailing_peak():
    spec = ProtectionSpec(
        trailing_stop_pct=0.003,
        trailing_activation_pct=0.01,
        trailing_rebase_on_scale_in=False,
    )
    state = ProtectionState.open(
        symbol="Crypto:BTC/USDT@spot",
        side="long",
        entry_price=100,
        spec=spec,
        opened_at="2026-01-01",
    )
    engine = ProtectionEngine()

    assert engine.evaluate_price(
        state,
        timestamp="2026-01-01 00:01:00",
        price=102,
    ) is None
    assert state.trailing_active is True
    assert state.highest_price == pytest.approx(102)

    state.apply_scale_in(
        entry_price=95,
        fill_price=90,
        spec=spec,
    )

    assert state.entry_price == pytest.approx(95)
    assert state.trailing_active is True
    assert state.highest_price == pytest.approx(102)
    decision = engine.evaluate_price(
        state,
        timestamp="2026-01-01 00:02:00",
        price=101.6,
    )
    assert decision is not None
    assert decision.reason == "trailing_stop"
    assert decision.trigger_price == pytest.approx(102 * (1 - 0.003))


def test_scale_in_rebases_unactivated_trailing_extremes_to_the_new_basket():
    spec = ProtectionSpec(
        trailing_stop_pct=0.003,
        trailing_activation_pct=0.05,
        trailing_rebase_on_scale_in=False,
    )
    state = ProtectionState.open(
        symbol="Crypto:BTC/USDT@spot",
        side="long",
        entry_price=100,
        spec=spec,
        opened_at="2026-01-01",
    )
    state.highest_price = 103

    state.apply_scale_in(
        entry_price=95,
        fill_price=90,
        spec=spec,
    )

    assert state.trailing_active is False
    assert state.highest_price == pytest.approx(95)
    assert state.lowest_price == pytest.approx(90)


def test_scale_in_defaults_to_legacy_trailing_reset_for_custom_strategies():
    spec = ProtectionSpec(
        trailing_stop_pct=0.003,
        trailing_activation_pct=0.01,
    )
    state = ProtectionState.open(
        symbol="Crypto:BTC/USDT@spot",
        side="long",
        entry_price=100,
        spec=spec,
        opened_at="2026-01-01",
    )
    state.highest_price = 103
    state.trailing_active = True

    state.apply_scale_in(
        entry_price=95,
        fill_price=90,
        scaled_at="2026-01-02",
    )

    assert state.trailing_active is False
    assert state.highest_price == pytest.approx(95)
    assert state.lowest_price == pytest.approx(90)
    assert state.opened_at == pd.Timestamp("2026-01-02")
