# Shared Smart Insights research implementation plan

> **For Codex:** Execute this plan inline in the current checkout. Preserve unrelated working-tree changes and stage only files owned by this feature.

**Goal:** Replace per-account Smart Insights report generation with a reusable report keyed by normalized asset, kind, and Vietnam reporting period. Common reports remain guest-readable; reports for non-common assets can only be read by signed-in users currently watching that asset.

**Architecture:** Keep the existing public-report table and publisher as the safe common-asset boundary, then add a separate shared-watchlist report store for non-common assets. A single authenticated resolver selects the appropriate source, verifies current watchlist membership for private scope on every read, and atomically claims a pending period before enqueueing work. The Smart Insights frontend receives server-projected report states rather than account-owned run data.

**Tech Stack:** Flask, PostgreSQL, Celery, Fast Analysis, TradingAgents, Vue 3, Vitest-compatible Node unit tests, pytest.

### Task 1: Define the shared-report contract and migration

**Files:**
- Create: `backend/backend_api_python/migrations/20260914_shared_watchlist_research_reports.sql`
- Create: `backend/backend_api_python/app/services/smart_insights/shared_reports.py`
- Create: `backend/backend_api_python/tests/test_shared_research_reports.py`

**Steps:**
1. Write failing repository/service tests for canonical asset keys, Vietnam daily/weekly period keys, atomic first-claim behavior, pending coalescing, current-period availability, and payload projection that excludes run IDs and request metadata.
2. Add a `shared_watchlist_research_reports` table with unique `(asset_key, report_kind, locale, period_key)` and status/payload/run fields; index latest reads and pending deep synchronization.
3. Implement repository methods for read, atomic claim, completion/failure transitions, and pending deep rows.
4. Implement safe DTO projection and report-state resolution. Never serialize initiator, private request, source run ID, artifact path, or account history references.
5. Run `pytest tests/test_shared_research_reports.py -q`; proceed only when green.

### Task 2: Build authorization-aware shared report orchestration

**Files:**
- Create: `backend/backend_api_python/app/services/smart_insights/shared_research_publisher.py`
- Modify: `backend/backend_api_python/app/services/smart_insights/public_reports.py`
- Modify: `backend/backend_api_python/app/services/smart_insights/public_research_publisher.py`
- Modify: `backend/backend_api_python/tests/test_shared_research_reports.py`
- Modify: `backend/backend_api_python/tests/test_public_research_reports.py`

**Steps:**
1. Add a canonical common-asset helper, without broadening the guest/public asset allowlist.
2. Implement a single service that resolves common assets from the existing public store and non-common assets from the shared-watchlist store.
3. On each authenticated read/create, verify the caller either targets a common asset or has a current exact `(market, symbol)` watchlist row. Deny missing membership with a non-disclosing not-found/forbidden response.
4. Add quick-generation orchestration that claims today before calling Fast Analysis and writes only a bounded sanitized payload.
5. Add deep-generation orchestration that claims this week before creating a system-principal TradingAgents run, synchronizes only the sanitized markdown projection, and coalesces duplicate requests.
6. Retain the public publisher for fixed common scheduled reports; reuse its sanitizers/system principal conventions so public and shared outputs have identical redaction guarantees.
7. Add tests proving common reports are resolvable by guests/accounts, shared reports are visible only to current watchers, duplicate claims do not enqueue twice, and no run identifier is exposed.

### Task 3: Add authenticated report-state, create, and PDF routes

**Files:**
- Modify: `backend/backend_api_python/app/routes/smart_insights.py`
- Create: `backend/backend_api_python/tests/test_shared_research_routes.py`
- Modify: `backend/backend_api_python/tests/test_smart_insights_guest_access.py`

**Steps:**
1. Write route tests for authenticated state reads, create/reuse semantics, cross-account current-watchlist authorization, and guest rejection for non-common routes.
2. Add an authenticated endpoint returning a safe state for each requested asset/report kind, plus a batch endpoint for the account’s common-plus-watchlist asset set.
3. Add authenticated create endpoints for quick and deep reports that return existing complete/pending reports instead of creating duplicates.
4. Add authenticated deep PDF and summary PDF endpoints rendered from the sanitized stored payload, never proxied from a user-owned TradingAgents artifact.
5. Keep existing `/public/*` routes public and fixed-scope; do not expose shared-watchlist assets through them.
6. Run the focused pytest route suites.

### Task 4: Replace the per-watchlist scheduler with common-only schedule and synchronization

**Files:**
- Modify: `backend/backend_api_python/app/celery_app.py`
- Modify: `backend/backend_api_python/app/tasks/smart_insights.py`
- Modify: `backend/backend_api_python/tests/test_celery_boundaries.py`
- Modify: `backend/backend_api_python/tests/test_daily_watchlist_ai_analysis.py`

**Steps:**
1. Write/update the Celery contract test to assert there is no daily all-watchlist Fast Analysis beat entry or routing key.
2. Remove the `daily-watchlist-ai-analysis` beat schedule and task route only; leave unrelated user-created monitors untouched.
3. Preserve daily common quick reports at 07:15 Asia/Ho_Chi_Minh, weekly common deep reports at Monday 08:00, and deep synchronization cadence.
4. Ensure task names and queues match actual publisher behavior.
5. Run Celery boundary and retained monitor tests.

### Task 5: Render common plus watchlist assets from shared report state

**Files:**
- Modify: `frontend/src/api/smart-insights.js`
- Modify: `frontend/src/views/smart-insights/watchlistOpinions.js`
- Modify: `frontend/src/views/smart-insights/index.vue`
- Modify: `frontend/src/views/smart-insights/components/AssetOpinionsSection.vue`
- Create: `frontend/src/views/smart-insights/components/SharedReportModal.vue`
- Modify: `frontend/tests/unit/smartInsightsWatchlistOpinions.test.mjs`
- Modify: `frontend/tests/unit/smartInsightsPageContract.test.mjs`

**Steps:**
1. Write failing unit tests for account asset union (common first, then unique watchlist assets), shared report state mapping, and create button visibility only when the current period has no pending/complete report.
2. Add authenticated API clients for state/list/create and protected deep PDF URLs.
3. Replace account-only opinions with common-plus-watchlist rows. Guests keep the existing fixed common asset surface.
4. Present quick reports in a readable modal and deep reports in the existing PDF-reader style, with an explicit open-in-new-tab action.
5. For signed-in users, show “Tạo nhận định” / “Tạo phân tích chuyên sâu” only for an eligible missing period; reload/poll state while pending. Existing state must be displayed instead of offering a duplicate action.
6. Preserve the restriction that guests cannot create reports and do not see non-common assets.
7. Run focused frontend unit tests and production build.

### Task 6: Verify, review, and prepare the release

**Files:**
- Review all files changed by this feature only.

**Steps:**
1. Run `git diff --check` and targeted backend/frontend test commands with a repo-local pytest temp parent if required.
2. Inspect API payload tests to prove that private identifiers and account-owned artifacts are not reachable.
3. Review `git status` and stage only the migration, backend, frontend, and tests listed above; leave generated and unrelated dirty files untouched.
4. Commit/push only if explicitly requested in a later message; otherwise report exact verification results and any environment-blocked checks.
