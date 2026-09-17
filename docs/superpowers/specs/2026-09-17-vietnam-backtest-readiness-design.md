# Vietnam Backtest and Portfolio Readiness Design

## Goal

Make HOSE daily history from the free VNDIRECT and Yahoo sources safe enough for 5-10 year research backtests and portfolio optimization without silently mixing raw and adjusted prices, future fundamentals, or current-only universe membership.

## Scope and sequencing

1. Canonical daily bars and price modes.
2. Observed HOSE trading-session filtering and quality gates.
3. Ten-year daily range support for backtests and optimizer inputs.
4. Point-in-time Vietnam fundamental bridge for Strategy V2.
5. Historical HOSE universe resolution.
6. Vietnam execution metadata for the existing simulation broker.

Only VNDIRECT and Yahoo are price providers. No paid provider or broker API is introduced. Existing Fast Analysis, AI Chat, TradingAgents, and realtime raw-price behavior remain compatible.

## Canonical daily price contract

Daily provider rows may carry `adjusted_close`, `adjustment_factor`, `price_mode`, and `quality_flags` in addition to normalized OHLCV. Yahoo `adjclose` supplies the factor used to adjust all OHLC fields. VNDIRECT rows are classified as raw/unknown-adjustment and must not satisfy an adjusted or total-return request by themselves.

`VNStockDataSource.get_kline` accepts `price_mode`:

- `raw`: select the first fresh valid provider as today.
- `adjusted`: require a provider row with a finite positive adjustment factor and return adjusted OHLC.
- `total_return`: same provider requirement as adjusted; retain the distinct mode in provenance so optimizer snapshots describe their return basis.

For adjusted modes the source may call VNDIRECT first to establish observed trading dates, then Yahoo for adjustment factors. Yahoo zero-volume daily rows are removed. When a VNDIRECT calendar is available, Yahoo rows outside that calendar are removed. Intraday supports only `raw`.

Selected daily bars are persisted best-effort in `qd_vietnam_daily_prices` with raw and adjusted OHLC, factor, source, observed time, quality flags, and checksum. Persistence failure must not make a public free-provider read fail.

## Quality and provenance

The source exposes the actual provider, attempts, price mode, coverage, and quality flags. Coverage for adjusted data is matched Yahoo sessions divided by observed VNDIRECT sessions when that reference exists. Otherwise it is nonzero-volume sessions divided by weekdays. Portfolio optimization rejects series below configurable `VN_OPTIMIZER_MIN_COVERAGE`, default `0.90`.

The cache key includes price mode. No cached raw series may satisfy adjusted or total-return requests.

## Backtest and optimizer integration

Strategy V2 requests `adjusted` daily data for VNStock and attaches execution metadata after frame normalization. The optimizer requests `total_return` and stores price mode and quality flags in its immutable input snapshot.

VNStock daily backtests allow 3,660 calendar days including warmup. Optimizer request windows also allow 3,660 calendar days while the numerical engine retains its 3,650-observation cap.

## Fundamental point-in-time bridge

When Vietnam Evidence persists normalized observations, it also builds period/availability snapshots for `qd_fundamental_snapshots`. Only facts sharing the same `period_end` and `available_at` are combined. Derived ROE and debt-to-equity use only those same-period facts. Current shares or current prices are never copied backward. Strategy V2 continues using its existing point-in-time forward-fill behavior.

## Historical universe behavior

Symbol-master universes resolve members using `listed_date <= as_of` and `delisted_date IS NULL OR delisted_date > as_of`. Range candidate selection returns all members whose listing interval overlaps the requested range. Current requests still require active symbols. This removes current-active filtering where historical rows are available; it does not claim to reconstruct delisted companies absent from the free catalog history.

## Vietnam execution metadata

Daily VNStock frames add configurable execution fields consumed by the existing broker:

- `lot_size`, default `100` shares.
- `settlement_sessions`, default `2` sessions.
- `sell_tax_rate`, default supplied by environment and recorded in results.
- conservative locked-limit flags only when OHLC are equal and the move from the prior close reaches the configured HOSE limit threshold.

The simulator must not sell unsettled shares. Existing commission and slippage remain explicit inputs; sell tax is separate. All defaults are configuration values so rule changes do not require rewriting historical provider adapters.

## Error handling

- Invalid price modes fail before provider calls.
- Adjusted/total-return requests fail closed when no adjusted provider survives filtering.
- Empty, duplicate, non-finite, non-positive, stale, or under-covered optimizer series fail before optimization.
- Data gaps remain explicit in provenance and persisted quality flags.

## Verification

Use strict TDD for each behavior. Focused tests cover provider adjustment, holiday filtering, cache separation, persistence payload, 10-year range boundaries, optimizer coverage, point-in-time fundamental bridging, historical universe membership, lot sizing, locked limits, sell tax, and settlement. Then run related regressions, backend quality checks, `py_compile`, and `git diff --check`. Live provider smoke is read-only and supplementary to deterministic tests.
