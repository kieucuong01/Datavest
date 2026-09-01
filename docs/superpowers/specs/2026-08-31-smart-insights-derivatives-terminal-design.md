# Smart Insights Derivatives Terminal Design

## Purpose

Build a research-first crypto derivatives tab for Smart Insights. It must help a long-horizon crypto investor understand positioning, futures carry, options risk, and stress context without presenting a trading instruction, a market-wide aggregate that cannot be defended, or invented history.

## Scope

- BTC, ETH, SOL: funding, open interest, long/short account ratio, taker buy/sell imbalance, and a descriptive price-versus-OI regime.
- BTC, ETH only: near/far annualized basis, futures term curve, call OI, put OI, put/call OI, and historical volatility.
- SOL options is explicitly `NOT_APPLICABLE`, never zero.
- CoinGlass max-pain and margin-borrow remain source-specific secondary snapshot context.

## Sources

| Source code | Provider | History policy |
| --- | --- | --- |
| `bybit-derivatives` | Bybit V5 public API | Paginate funding/OI/ratio to the earliest record returned per symbol. |
| `binance-usdm-derivatives` | Binance USD-M public API | Paginate funding; limit OI/taker/basis to the documented 30-day window. |
| `deribit-public-derivatives` | Deribit public JSON-RPC | Backfill returned historical volatility; begin daily curve and options snapshots now. |
| existing CoinGlass sources | Browser Use | Preserve snapshots; no retroactive history claim. |

Existing `openbb-deribit` remains an explicit fallback until the direct Deribit collector has runtime evidence.

## Data policy

- Normalise all persisted observations to a UTC daily effective date.
- Use the existing checksum upsert: reruns are idempotent.
- Backfill commands accept source codes and a date range; each provider returns actual coverage metadata: source, metric, symbol, start, end, and `historyLimited`.
- A daily job runs at 00:40 UTC, re-fetches the prior seven UTC days, and a 02:15 UTC retry targets only failed sources.
- Invalid or unavailable provider values yield unavailable/partial state; never persist a synthetic zero.
- Source values remain venue-specific; do not calculate an unlabelled cross-exchange average.

## API contract

Add `tabs.sentimentDerivatives.derivatives` without breaking legacy `metrics` and `series`:

```json
{
  "status": "AVAILABLE",
  "assets": ["BTC", "ETH", "SOL"],
  "coverage": [{"source": "bybit-derivatives", "metric": "crypto.derivatives.perpetual.open_interest_usd", "symbol": "BTC", "start": "2020-07-20T00:00:00Z", "end": "2026-08-31T00:00:00Z", "historyLimited": false}],
  "series": [],
  "latest": [],
  "stress": []
}
```

Each latest/series item carries source, metric, symbol, effectiveAt, value, unit, dimensions, and evidenceId.

## UI

Create `DerivativesTerminal.vue` and render it exclusively for the Phái sinh tab.

1. Header: terminal title, educational subtitle, BTC/ETH/SOL selector, 30D/90D/1Y/All range control, freshness badge, and data-coverage disclosure.
2. Full-width primary ECharts combo: price line plus OI-change bars, zero line, source legend, and hover tooltip with date, venue, unit, and value.
3. Positioning cards: annualized funding, OI 7-day change, long/short ratio, taker imbalance.
4. Full-width funding chart with positive/negative area around zero.
5. BTC/ETH carry and options panels: basis/term curve, put/call OI plus historical volatility.
6. De-emphasized CoinGlass stress cards marked as snapshots.
7. Empty state distinguishes `UNAVAILABLE`, `BACKFILLING`, `WINDOW_LIMITED`, and `NOT_APPLICABLE`.

Use existing ECharts patterns. Do not use `grid-column: 1 / -1`; the project minifier has previously corrupted that shorthand.

## Non-goals

No orders, leverage recommendations, liquidation predictions, paid API requirement, secret API keys, or intraday scheduler in v1.

## Acceptance criteria

- Dedicated interactive terminal replaces generic Phái sinh cards.
- BTC/ETH/SOL positioning is source-labelled; BTC/ETH options work; SOL options is clearly inapplicable.
- Initial import is idempotent and coverage-aware.
- Daily and retry schedules are narrow and source-failure tolerant.
- Focused backend/UI tests, local backfill evidence, frontend build, and browser inspection are completed before delivery.
