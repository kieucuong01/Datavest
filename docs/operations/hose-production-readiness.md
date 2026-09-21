# HOSE production readiness

The operator endpoint `GET /api/market/ops/hose-readiness` is admin-only. It exposes only aggregate catalog, EOD price, fundamental and provider-health state.

- Catalog: at least `HOSE_SNAPSHOT_MIN_ROWS` active VNDIRECT-backed HOSE equity/ETF symbols.
- Daily prices: at least 95% of active symbols from the most recent EOD batch. The job runs at 16:25 Asia/Ho_Chi_Minh; set `HOSE_EOD_MIN_COVERAGE` only after an explicit operational review.
- Fundamentals: counts are observational. A missing value is a data gap, not a neutral score or a current-value backfill.
- Provider health: VNDIRECT is primary; Yahoo is a bounded fallback. Yahoo 429/5xx may degrade health but must not replace a valid VNDIRECT series.

If the endpoint is `attention_required`, retain the last known good persisted data and investigate provider health before advertising wider HOSE backtest or optimizer coverage.
