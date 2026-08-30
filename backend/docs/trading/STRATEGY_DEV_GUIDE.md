# QuantDinger Strategy Development Guide

> Scope: Strategy API V2 research, validation, factor analysis, and backtesting

A QuantDinger strategy is a Python program for research and backtesting. It can declare market-data subscriptions, generate signals from completed bars, and evaluate positions, protection rules, and performance in an isolated simulation ledger.

The central boundary is: **strategy source does not connect to user accounts or submit orders to external venues.**

## 1. Recommended workflow

1. Select instruments and frequencies using public or authorized read-only market data.
2. Write Strategy API V2 source and run static validation.
3. Backtest over a fixed data range.
4. Review fill assumptions, fees, slippage, drawdown, and out-of-sample behavior.
5. Use alerts, notifications, or a paper portfolio for continued observation; those surfaces still have no external execution authority.

## 2. Minimal strategy

```python
def initialize(context):
    context.symbol = "BTC/USDT"


def handle_data(context, data):
    close = data.history(context.symbol, "close", 20)
    if len(close) < 20:
        return

    average = close.mean()
    if close.iloc[-1] > average:
        order_target_percent(context.symbol, 1.0)
    else:
        order_target_percent(context.symbol, 0.0)
```

Functions such as `order_target_percent` create simulated order intents that the backtest ledger processes. They do not represent external orders.

## 3. Data and time semantics

- Calculate signals from completed bars only; avoid look-ahead behavior.
- Declare the market, canonical instrument, and frequency explicitly.
- The backtest clock comes from market data; no account or network clock is available.
- Public crypto market-data clients carry no user credentials.
- Research code cannot read account balances, external positions, user secrets, or private order state.

## 4. Signals, portfolios, and protections

Strategy API V2 can express long/short signals, target positions, stops, profit targets, and portfolio constraints inside simulation. All state belongs to a research or backtest run.

A strategy should:

- make entry, sizing, reduction, and exit rules reproducible;
- advance state from confirmed simulated fills;
- state fee, slippage, minimum-size, and liquidity assumptions;
- disclose material limitations that cannot be modeled;
- avoid promising returns or presenting historical results as guarantees.

## 5. Converting an Indicator

An Indicator's `output["signals"]` contains chart markers. During conversion, define what each visual event means:

- an explicit bullish entry event may map to `open_long`;
- an explicit bearish exit event may map to `close_long`;
- create short-entry logic only when the requirement and rule are explicit;
- never infer reversal behavior from a marker label alone.

Validate the converted source and compare event indexes on a fixed OHLCV fixture.

## 6. Backtest acceptance

At minimum, review:

- data range, timezone, adjustment method, and missing data;
- whether every signal uses only information available at that time;
- fees, slippage, fill price, and position limits;
- total return, maximum drawdown, trade count, and exposure;
- in-sample versus out-of-sample behavior;
- parameter sensitivity instead of retaining only the best result.

A backtest is research evidence, not a performance promise. Research results, AI output, and paper portfolios are not investment advice.

## 7. Agent and MCP boundary

Agent Tokens use only R/W/B/N scopes for research, backtests, Indicators, alerts, watchlists, and paper portfolios. MCP clients do not receive user account secrets and cannot invoke external execution.

When adding a strategy tool, update Agent OpenAPI, MCP declarations, and contract tests while preserving this boundary.
