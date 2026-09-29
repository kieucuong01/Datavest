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

## Fundamental annual coverage (5–10 years)

The VNDIRECT financial-statement adapter requests the current year plus the preceding ten fiscal years, follows all result pages, excludes estimates, and retains only mapped financial metrics. `VietnamEvidence.fundamentals.annualCoverage` reports available and missing fiscal years for each metric and for each provider-reported statement scope. It uses only observations whose `periodEnd` and `availableAt` precede the analysis cutoff. A metric never observed by the provider is `not_observed`; that does **not** prove the metric is inapplicable. A partially covered observed metric adds `fundamentalHistory` to `dataGaps`.

Read-only sample on 2026-09-29, for completed fiscal years 2016–2025:

| Symbol | 10-year annual metrics present | Explicit gaps |
| --- | --- | --- |
| FPT | Revenue, net income, shareholder equity, total debt, operating cash flow: 10/10 years | EPS: 8/10 years; statement scope unknown |
| VCB | Total operating income, net income, shareholder equity, total debt, operating cash flow: 10/10 years | Revenue and EPS not observed; statement scope unknown |

For banks, `total_operating_income` is a distinct metric; it must not be silently substituted for corporate `revenue`. The source's `createdDate` is used as a provider-reported `availableAt` proxy, but it is **not a verified exchange filing timestamp**. In this sample, FPT's FY2016 revenue row has provider `availableAt` in November 2019, so it is not eligible for a 2016–2018 point-in-time backtest. The public endpoint has no published availability SLA or guaranteed historical point-in-time revision contract. These spot checks do not establish coverage for every HOSE symbol or make historical fundamentals automatically safe for backtesting. If the endpoint is blocked or incomplete, preserve the data gap; do not backfill from current values or forecast rows. VNDIRECT's public [DStock](https://dstock.vndirect.com.vn/) is a reference display, while [HOSE disclosures](https://www.hsx.vn/) remain the primary place to verify original filings.
