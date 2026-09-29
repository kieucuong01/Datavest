# HOSE production readiness

The operator endpoint `GET /api/market/ops/hose-readiness` is admin-only. It exposes only aggregate catalog, EOD price, fundamental and provider-health state.

- Catalog: at least `HOSE_SNAPSHOT_MIN_ROWS` active VNDIRECT-backed HOSE equity/ETF symbols.
- Daily prices: at least 95% of active symbols from the most recent EOD batch. The job runs at 16:25 Asia/Ho_Chi_Minh; set `HOSE_EOD_MIN_COVERAGE` only after an explicit operational review.
- Fundamentals: counts are observational. A missing value is a data gap, not a neutral score or a current-value backfill.
- Provider health: VNDIRECT is primary; Yahoo is a bounded fallback. Yahoo 429/5xx may degrade health but must not replace a valid VNDIRECT series.

If the endpoint is `attention_required`, retain the last known good persisted data and investigate provider health before advertising wider HOSE backtest or optimizer coverage.

## Historical daily coverage (5–10 years)

For research backtests and optimization, coverage means **distinct local HOSE trading days returned / weekdays in the requested window**. Weekdays are an approximation (public sources do not provide a complete holiday calendar), so normal holiday gaps reduce the ratio. The provider's own `last_kline_quality.coverage` measures overlap with its reference calendar; it is not proof that the requested years are present. The optimizer uses the lower of both measures and rejects below `VN_OPTIMIZER_MIN_COVERAGE` (default 0.90). Strategy V2 daily backtests reject under-covered VNStock frames below `VN_BACKTEST_MIN_COVERAGE` (default 0.90). The bounded backfill report uses the same distinct-day window calculation and marks incomplete history as a data gap.

Read-only provider sample on 2026-09-29 for windows ending 2026-09-28, after OHLCV validation and removal of zero-volume bars:

| Symbol | 5-year bars / coverage | 10-year bars / coverage |
| --- | ---: | ---: |
| FPT | 1,224 / 93.87% | 2,431 / 93.21% |
| HPG | 1,226 / 94.02% | 2,431 / 93.21% |
| VCB | 1,225 / 93.94% | 2,413 / 92.52% |

Yahoo returned adjusted-close factors on every retained bar in this sample. VNDIRECT's daily-history endpoint returned HTTP 406 in the same check; the full FPT 10-year `VNStockDataSource` request selected `yahoo-vn` after attempting both providers. This verifies the sampled symbols and dates, **not** all HOSE symbols or a guaranteed provider SLA. Recheck source availability and window coverage before relying on a new backtest date range or newly listed symbol.
