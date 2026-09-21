# HOSE Production Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make HOSE research features fail safely and operate from monitored, durable free-source data before representing them as ready for all active HOSE securities.

**Architecture:** Keep the VNDIRECT-first/Yahoo-fallback adapter and immutable Vietnam Evidence DTO. Add deterministic source-health and data-coverage records, use them to make TradingAgents retries diagnosable, and use the active HOSE symbol master as the validation boundary for every research/portfolio input. Historical price and fundamental ingestion remain point-in-time and are scheduled work, never a request-time guess.

**Tech Stack:** Flask, Celery, PostgreSQL, Python/pytest, Vue 2/node:test, VNDIRECT and Yahoo public HTTP endpoints.

**Spec:** `docs/superpowers/specs/2026-09-17-vietnam-backtest-readiness-design.md`, `docs/superpowers/specs/2026-09-17-tradingagents-hose-evidence-design.md`, `docs/superpowers/specs/2026-09-21-hose-ai-provenance-design.md`

## Global Constraints

- Research and paper-investing only; no broker execution or paid provider.
- VNDIRECT is primary; Yahoo is a bounded fallback and never a source of invented freshness.
- Every HOSE market claim retains provider, market observation time, fetch time, coverage and explicit gaps.
- Inactive/delisted/non-HOSE symbols must not enter AI, TradingAgents, optimizer, manual portfolio, or historical ingestion.
- Do not publish a price/fundamental result as complete when the data contract is unavailable.

## Review Focus

- Yahoo 429/5xx must leave VNDIRECT data usable and surface a source-health failure, rather than erase a last-known-good series.
- A resumed TradingAgents run must reuse a write-once evidence snapshot; it must not rebuild from newer observations.
- A full-universe job must not deactivate catalog rows or persist a partial price batch after a provider outage.
- Historical fundamental enrichment must use only reports whose `available_at` is on/before the bar date.
- Portfolio and manual-position endpoints must reject an inactive HOSE symbol even when it has syntactically valid ticker characters.

---

### Task 1: TradingAgents HOSE failure classification and safe retry

**Files:**
- Modify: `backend/backend_api_python/app/tasks/trading_agents.py`
- Modify: `backend/backend_api_python/app/services/trading_agents_repository.py`
- Modify: `backend/backend_api_python/app/routes/trading_agents.py`
- Test: `backend/backend_api_python/tests/test_trading_agents_tasks.py`
- Test: `backend/backend_api_python/tests/test_trading_agents_routes.py`

**Interfaces:**
- Consumes: immutable `evidence_json` stored on `trading_agents_runs`.
- Produces: terminal `failure_code` in `{evidence_unavailable, service_rejected, runner_failed}` plus a bounded user-visible retryability field.

- [ ] Write failing tests proving an evidence-provider failure is classified as `evidence_unavailable`, a signed service rejection becomes `service_rejected`, and a retryable failure exposes safe provenance without a raw traceback.
- [ ] Run the focused tests and observe the missing/incorrect classification.
- [ ] Implement a single classifier used by task persistence and the public run projection; preserve an already-stored HOSE evidence snapshot on retry.
- [ ] Run focused TradingAgents tests, then the backend TradingAgents regression group.
- [ ] Commit with `fix: classify HOSE TradingAgents failures`.

### Task 2: HOSE provider-health and durable EOD coverage service

**Files:**
- Create: `backend/backend_api_python/app/services/vietnam_market_health.py`
- Modify: `backend/backend_api_python/app/data_sources/vn_stock.py`
- Modify: `backend/backend_api_python/app/celery_app.py`
- Create: `backend/backend_api_python/app/tasks/vietnam_market_data.py`
- Modify: `backend/backend_api_python/app/services/vietnam_market_history.py`
- Test: `backend/backend_api_python/tests/test_vietnam_market_health.py`
- Test: `backend/backend_api_python/tests/test_vn_stock.py`

**Interfaces:**
- Consumes: `VNStockDataSource.get_kline(symbol, "1D", ..., price_mode)` and active HOSE catalog rows.
- Produces: idempotent source-health snapshots and a per-symbol EOD ingestion result with provider/attempts/coverage/flags.

- [ ] Write failing tests for a VNDIRECT success plus Yahoo 429, all-provider failure, minimum batch coverage, and no persistence for incomplete full-universe batches.
- [ ] Run them red.
- [ ] Implement health records and a Celery EOD task that reads active HOSE rows, writes only validated daily selections, and reports exact coverage/gaps.
- [ ] Schedule the task after the Vietnamese EOD window; retain request-time cache behavior unchanged.
- [ ] Run focused market-data tests and migrations/quality checks; commit with `feat: monitor HOSE EOD data coverage`.

### Task 3: Historical HOSE price/fundamental ingestion and point-in-time coverage

**Files:**
- Modify: `backend/backend_api_python/app/services/vietnam_evidence.py`
- Modify: `backend/backend_api_python/app/services/fundamental_data.py`
- Modify: `backend/backend_api_python/app/tasks/vietnam_market_data.py`
- Modify: `backend/backend_api_python/app/services/backtest_limits.py`
- Test: `backend/backend_api_python/tests/test_vietnam_evidence.py`
- Test: `backend/backend_api_python/tests/test_fundamental_data.py`
- Test: `backend/backend_api_python/tests/test_strategy_v2_service.py`

**Interfaces:**
- Consumes: VNDIRECT statement observations with `periodEnd`, `availableAt`, scope and source.
- Produces: complete point-in-time snapshots for VNStock and a backfill result that names unavailable historical periods instead of fabricating them.

- [ ] Write failing tests for Vietnam `sync_history`, report availability cutoffs, quarterly/annual scope, and a ten-year request that records an explicit coverage gap when history is incomplete.
- [ ] Run them red.
- [ ] Implement VN fundamental history ingestion using the Evidence normalizer; never assign current values to historical bars.
- [ ] Add resumable bounded backfill cursors for price and fundamental jobs; default to no automatic ten-year full scan on web requests.
- [ ] Run the relevant strategy/backtest/optimizer tests; commit with `feat: backfill point-in-time HOSE research data`.

### Task 4: Enforce HOSE symbol master outside AI

**Files:**
- Modify: `backend/backend_api_python/app/services/portfolio_optimizer/service.py`
- Modify: `backend/backend_api_python/app/routes/portfolio.py`
- Modify: `frontend/src/views/portfolio-optimizer/index.vue`
- Modify: `frontend/src/views/mock-portfolio/index.vue`
- Test: `backend/backend_api_python/tests/test_portfolio_optimizer_service.py`
- Test: `backend/backend_api_python/tests/test_portfolio.py`
- Test: `frontend/tests/unit/hosePresentation.test.mjs`

**Interfaces:**
- Consumes: `validate_hose_ai_target("VNStock", symbol)` and `/api/market/symbols/search?market=VNStock&exchange=HOSE`.
- Produces: active-HOSE-only optimizer/position requests and selector results with symbol, company, HOSE and VND.

- [ ] Write failing backend tests for inactive/delisted/non-HOSE optimizer and manual-position inputs; write frontend contract tests that the VN selectors search server-side instead of accepting a fabricated result.
- [ ] Run red tests.
- [ ] Apply the shared validation in server request parsing and use the existing catalog search endpoint for the two Vue forms.
- [ ] Run focused backend/frontend tests and full frontend unit tests; commit with `feat: enforce active HOSE portfolio instruments`.

### Task 5: Operator visibility and release verification

**Files:**
- Modify: `backend/backend_api_python/app/routes/market.py`
- Modify: `backend/backend_api_python/app/services/market_catalog_sync.py`
- Test: `backend/backend_api_python/tests/test_market_catalog_sync.py`
- Test: `backend/backend_api_python/tests/test_market.py`
- Modify: `docs/operations/hose-production-readiness.md`

**Interfaces:**
- Consumes: EOD health, catalog sync, price coverage, VN fundamental coverage and TradingAgents run aggregates.
- Produces: authenticated operator summary with no provider secrets or raw user data.

- [ ] Write failing tests for a safe HOSE readiness summary and stale/partial catalog status.
- [ ] Run red tests.
- [ ] Implement the summary and operational runbook with thresholds for catalog, daily price, fundamentals and TradingAgents success.
- [ ] Run backend suite, frontend suite, `git diff --check`, Graphify update, and read-only production provider/health smoke.
- [ ] Commit with `feat: expose HOSE readiness operations`.
