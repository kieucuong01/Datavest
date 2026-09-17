# Vietnam Backtest and Portfolio Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make free VNDIRECT/Yahoo HOSE daily data safe for 5-10 year research backtests and portfolio optimization.

**Architecture:** Add explicit raw/adjusted/total-return modes at the Vietnam adapter boundary, persist canonical daily bars, and propagate quality/provenance to Strategy V2 and optimizer inputs. Reuse existing point-in-time fundamental and universe contracts, and feed Vietnam execution metadata into the generic broker.

**Tech Stack:** Python 3, Flask services, PostgreSQL migrations, pandas, NumPy, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-vietnam-backtest-readiness-design.md`

## Global Constraints

- Price providers remain free VNDIRECT plus Yahoo only.
- Realtime and legacy callers default to raw prices.
- Adjusted and total-return requests fail closed instead of falling back to raw prices.
- Historical facts use `available_at`; universe membership uses listing intervals.
- Work sequentially in the current linked worktree; do not spawn subagents.
- Do not commit, push, or deploy unless the user explicitly requests it.

---

### Task 1: Canonical daily prices, adjustment, and quality

**Files:**
- Create: `backend/backend_api_python/app/services/vietnam_market_history.py`
- Create: `backend/backend_api_python/migrations/20260917_vietnam_daily_prices.sql`
- Modify: `backend/backend_api_python/migrations/init.sql`
- Modify: `backend/backend_api_python/app/data_sources/vn_market_providers.py`
- Modify: `backend/backend_api_python/app/data_sources/vn_stock.py`
- Test: `backend/backend_api_python/tests/test_vn_market_data.py`

**Interfaces:**
- Produces `normalize_price_mode(value)`, `select_vietnam_daily_bars(provider_results, price_mode)`, `VietnamDailyPriceRepository.persist(...)`, and optional bar keys `adjusted_close`, `adjustment_factor`, `quality_flags`.

- [x] Add tests proving Yahoo adjustment factors transform all OHLC values, zero-volume daily rows are rejected, adjusted requests use VNDIRECT dates plus Yahoo adjusted values, raw/adjusted cache entries are isolated, and canonical rows are persisted with checksums.
- [x] Run the focused tests and confirm failures are caused by missing price-mode behavior.
- [x] Implement the smallest provider, selector, repository, migration, and source changes that pass.
- [x] Run the focused tests and existing Vietnam market tests.

### Task 2: Backtest and optimizer ten-year integration

**Files:**
- Modify: `backend/backend_api_python/app/data_sources/factory.py`
- Modify: `backend/backend_api_python/app/services/strategy_v2/market_data.py`
- Modify: `backend/backend_api_python/app/services/backtest_limits.py`
- Modify: `backend/backend_api_python/app/services/portfolio_optimizer/market_data.py`
- Modify: `backend/backend_api_python/app/services/portfolio_optimizer/quantdinger_gateway.py`
- Modify: `backend/backend_api_python/app/services/portfolio_optimizer/service.py`
- Test: `backend/backend_api_python/tests/test_backtest_limits.py`
- Test: `backend/backend_api_python/tests/test_strategy_v2_market_data.py`
- Test: `backend/backend_api_python/tests/test_portfolio_optimizer_vn_market_data.py`
- Test: `backend/backend_api_python/tests/test_portfolio_optimizer_service.py`

**Interfaces:**
- Consumes Vietnam `price_mode` and source quality metadata.
- Produces `PriceSeries.price_mode` and `PriceSeries.quality_flags` in optimizer snapshots.

- [x] Add failing tests for 3,660-day VN daily policy, adjusted Strategy V2 requests, total-return optimizer requests, minimum coverage rejection, and a 3,660-day optimizer request.
- [x] Run the focused tests and verify the intended failures.
- [x] Propagate price mode/provenance and change only VN daily/calendar-window limits.
- [x] Run the focused and optimizer regression suites.

### Task 3: Vietnam fundamental point-in-time bridge

**Files:**
- Modify: `backend/backend_api_python/app/services/vietnam_evidence.py`
- Test: `backend/backend_api_python/tests/test_vietnam_evidence.py`
- Test: `backend/backend_api_python/tests/test_fundamental_data.py`

**Interfaces:**
- Consumes Vietnam Evidence observations.
- Produces same-period rows in `qd_fundamental_snapshots` compatible with `FundamentalDataService.enrich_panel`.

- [x] Add a failing repository test showing quarterly observations become a point-in-time fundamental snapshot without borrowing current shares or prices.
- [x] Verify the test fails because no bridge insert exists.
- [x] Add grouped snapshot persistence and same-period ROE/debt-to-equity derivation.
- [x] Run evidence and fundamental regression tests.

### Task 4: Historical HOSE universe resolution

**Files:**
- Modify: `backend/backend_api_python/app/services/universe.py`
- Test: `backend/backend_api_python/tests/test_universe_contract.py`

**Interfaces:**
- Produces symbol-master member resolution by listing interval for an `as_of` date or an overlapping range.

- [x] Add failing tests for a currently inactive symbol that was listed during the historical date and for exclusion before listing/after delisting.
- [x] Verify failures demonstrate current-active survivorship filtering.
- [x] Apply date-aware symbol-master queries to `resolve_members` and `candidate_members`.
- [x] Run universe and Strategy V2 service regressions.

### Task 5: HOSE execution metadata and settlement

**Files:**
- Create: `backend/backend_api_python/app/services/vietnam_execution.py`
- Modify: `backend/backend_api_python/app/services/strategy_v2/market_data.py`
- Modify: `backend/backend_api_python/app/services/strategy_v2/runtime.py`
- Modify: `backend/backend_api_python/env.example`
- Test: `backend/backend_api_python/tests/test_strategy_v2_market_data.py`
- Test: `backend/backend_api_python/tests/test_strategy_v2_runtime.py`

**Interfaces:**
- Produces `enrich_vietnam_execution_frame(frame)` with lot, settlement, tax, and conservative locked-limit fields.
- Broker consumes bar `settlement_sessions` and `sell_tax_rate` while preserving non-Vietnam behavior.

- [x] Add failing tests for 100-share lots, locked-limit detection, sell-tax accounting, and rejection/deferment of selling unsettled purchases.
- [x] Verify each behavior fails for the expected missing contract.
- [x] Implement configurable metadata and a minimal trading-session settlement ledger.
- [x] Run Strategy V2 market-data/runtime regressions.

### Task 6: Integrated verification

**Files:**
- Verify all modified Python, SQL, and tests.

**Interfaces:**
- Consumes all earlier deliverables and produces verification evidence only.

- [x] Run all Vietnam, optimizer, backtest-limit, universe, fundamental, and Strategy V2 focused tests.
- [x] Run backend quality checks and the complete backend test suite.
- [x] Run `py_compile` for modified Python files and `git diff --check`.
- [x] Perform read-only 5-year and 10-year FPT live smokes for raw and total-return modes when network access is available.
