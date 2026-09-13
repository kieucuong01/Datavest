# Public Guest Research Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Publish a daily quick report and a weekly deep report for BTC, VNINDEX and XAU so guests can read them without accessing account-owned research.

**Architecture:** A new `public_research_reports` table stores final, safe report projections separately from user history. Dedicated Celery jobs generate them under a disabled non-login system principal, while public Smart Insights endpoints expose only the copied projection. Authenticated Smart Insights continues to use the current account's watchlist and private reports.

**Tech Stack:** Flask, PostgreSQL, Celery Beat, FastAnalysis, TradingAgents, Vue 2, Ant Design Vue, pytest, pnpm.

**Spec:** `docs/superpowers/specs/2026-09-13-public-guest-research-design.md`

## Global Constraints

- Public asset scope is exactly `Crypto:BTC/USDT`, `VNStock:VNINDEX`, and `Forex:XAUUSD`.
- Generated locale is `vi-VN`; locale remains a persisted field for future releases.
- Guest read APIs accept neither user IDs nor arbitrary assets/run IDs and never return prompts, artifacts, paths, provider settings or account data.
- A failed run retains the most recent completed public report as a dated fallback.
- Beat schedules run at 07:15 daily and 08:00 Monday weekly in `Asia/Ho_Chi_Minh`.

---

### Task 1: Public report persistence and safe projection

**Files:**

- Create: `backend/backend_api_python/migrations/20260913_public_research_reports.sql`
- Create: `backend/backend_api_python/app/services/smart_insights/public_reports.py`
- Create: `backend/backend_api_python/tests/test_public_research_reports.py`

**Interfaces:**

- Consumes: `PUBLIC_ASSET_SCOPE` from `public_access.py`.
- Produces: `PublicResearchReportsRepository.upsert_pending`, `complete`, `fail`, `latest`; `PublicResearchReportsService.get_latest(asset_key, report_kind, locale='vi-VN')`; and `public_projection(row)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_latest_rejects_assets_outside_the_fixed_public_scope():
    service = PublicResearchReportsService(repository=FakeRepository())
    assert service.get_latest("crypto:BTC/USDT", "quick") is not None
    with pytest.raises(ValueError, match="unsupported_public_asset"):
        service.get_latest("crypto:ETH/USDT", "quick")

def test_failed_current_period_returns_the_previous_completed_projection():
    service = PublicResearchReportsService(repository=FakeRepository(
        completed_for="2026-09-12", failed_for="2026-09-13"
    ))
    result = service.get_latest("crypto:BTC/USDT", "quick")
    assert result["effectiveDate"] == "2026-09-12"
    assert result["isFallback"] is True

def test_projection_drops_private_fields():
    row = {"payload": {"title": "BTC", "body": "safe", "prompt": "secret", "runId": "private"}}
    assert PublicResearchReportsService.public_projection(row) == {"title": "BTC", "body": "safe"}
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
& ".\.test_deps\Scripts\python.exe" -m pytest backend_api_python/tests/test_public_research_reports.py -q --basetemp .pytest-public-research-red
```

Expected: failure because the public report module is absent.

- [ ] **Step 3: Implement the smallest durable store**

```sql
CREATE TABLE IF NOT EXISTS public_research_reports (
    id BIGSERIAL PRIMARY KEY,
    asset_key VARCHAR(120) NOT NULL,
    report_kind VARCHAR(16) NOT NULL CHECK (report_kind IN ('quick', 'deep')),
    locale VARCHAR(16) NOT NULL DEFAULT 'vi-VN',
    effective_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('pending', 'complete', 'failed')),
    payload_json JSONB,
    failure_code VARCHAR(80),
    source_run_id VARCHAR(128),
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (asset_key, report_kind, locale, effective_date)
);
```

Validate kind, locale, date and canonical asset key before database access. Persist raw private identifiers only in `source_run_id`; never include them in `payload_json`. `public_projection` allowlists `title`, `summary`, `body`, `sections`, `decision`, `confidence`, `provenance`, `effectiveDate`, and `generatedAt`.

- [ ] **Step 4: Run the test and verify GREEN**

Run:

```powershell
& ".\.test_deps\Scripts\python.exe" -m pytest backend_api_python/tests/test_public_research_reports.py -q --basetemp .pytest-public-research-green
```

Expected: all public persistence tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/backend_api_python/migrations/20260913_public_research_reports.sql backend/backend_api_python/app/services/smart_insights/public_reports.py backend/backend_api_python/tests/test_public_research_reports.py
git commit -m "feat: add public research report store"
```

### Task 2: Bounded unauthenticated read routes

**Files:**

- Modify: `backend/backend_api_python/app/services/smart_insights/public_access.py`
- Modify: `backend/backend_api_python/app/routes/smart_insights.py`
- Modify: `backend/backend_api_python/tests/test_smart_insights_mvp_scope.py`
- Modify: `backend/backend_api_python/tests/test_public_research_reports.py`

**Interfaces:**

- Consumes: Task 1 `PublicResearchReportsService`.
- Produces: `GET /api/smart-insights/public/reports` and `GET /api/smart-insights/public/reports/<asset_key>/<report_kind>`.

- [ ] **Step 1: Write failing API tests**

```python
def test_guest_reads_a_fixed_scope_public_report(client, monkeypatch):
    monkeypatch.setattr(public_access, "get_public_research_reports_service", lambda: FakeReports())
    response = client.get("/api/smart-insights/public/reports/crypto:BTC%2FUSDT/quick")
    assert response.status_code == 200
    assert response.get_json()["data"]["assetKey"] == "crypto:BTC/USDT"

def test_public_report_route_rejects_an_arbitrary_asset_and_never_echoes_a_run_id(client):
    response = client.get("/api/smart-insights/public/reports/crypto:ETH%2FUSDT/quick?runId=private")
    assert response.status_code == 404
    assert "private" not in response.get_data(as_text=True)
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
& ".\.test_deps\Scripts\python.exe" -m pytest backend_api_python/tests/test_smart_insights_mvp_scope.py backend_api_python/tests/test_public_research_reports.py -q --basetemp .pytest-public-api-red
```

Expected: 404 because the new public route is absent.

- [ ] **Step 3: Implement fixed-scope public access**

```python
@smart_insights_blp.route("/public/reports/<path:asset_key>/<string:report_kind>", methods=["GET"])
def public_report(asset_key: str, report_kind: str):
    try:
        result = get_public_smart_insights_service().get_public_report(
            asset_key=asset_key, report_kind=report_kind, locale=_locale()
        )
        return _ok(result) if result is not None else _fail("public_report_not_found", 404)
    except ValueError:
        return _fail("public_report_not_found", 404)
```

The list endpoint must iterate from `PUBLIC_ASSET_SCOPE`, not client input. It returns only Task 1 projections and preserves current private `/overview` and `/dates` decorators.

- [ ] **Step 4: Run the route and scope suites**

Run:

```powershell
& ".\.test_deps\Scripts\python.exe" -m pytest backend_api_python/tests/test_smart_insights_mvp_scope.py backend_api_python/tests/test_public_research_reports.py -q --basetemp .pytest-public-api-green
```

Expected: public route and existing account-scope tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/backend_api_python/app/services/smart_insights/public_access.py backend/backend_api_python/app/routes/smart_insights.py backend/backend_api_python/tests/test_smart_insights_mvp_scope.py backend/backend_api_python/tests/test_public_research_reports.py
git commit -m "feat: expose safe public research reports"
```

### Task 3: Publisher, system principal, and Celery schedules

**Files:**

- Modify: `backend/backend_api_python/app/services/fast_analysis.py`
- Create: `backend/backend_api_python/app/services/smart_insights/public_research_publisher.py`
- Modify: `backend/backend_api_python/app/tasks/smart_insights.py`
- Modify: `backend/backend_api_python/app/celery_app.py`
- Modify: `backend/backend_api_python/migrations/20260913_public_research_reports.sql`
- Create: `backend/backend_api_python/tests/test_public_research_publisher.py`
- Modify: `backend/backend_api_python/tests/test_celery_boundaries.py`

**Interfaces:**

- Consumes: Task 1 store; `FastAnalysisService.analyze`; `TradingAgentsRepository.create_run`; `enqueue_trading_agents_run`; `fetch_artifact_from_service`.
- Produces: `publish_daily_public_quick_reports`, `enqueue_weekly_public_deep_reports`, `sync_public_deep_reports`; Celery tasks `datavest.tasks.publish_public_quick_reports`, `datavest.tasks.enqueue_public_deep_reports`, `datavest.tasks.sync_public_deep_reports`.

- [ ] **Step 1: Write failing publisher tests**

```python
def test_daily_publisher_uses_only_public_assets_and_does_not_persist_personal_history():
    fast = FakeFastAnalysis()
    publisher = PublicResearchPublisher(reports=FakeReports(), fast_analysis=fast)
    publisher.publish_daily_quick_reports(today="2026-09-13")
    assert [(item["market"], item["symbol"], item["persist_history"]) for item in fast.calls] == [
        ("Crypto", "BTC/USDT", False), ("VNStock", "VNINDEX", False), ("Forex", "XAUUSD", False)
    ]

def test_deep_sync_copies_only_safe_complete_report_content():
    publisher = PublicResearchPublisher(reports=FakeReports(), trading_agents=FakeTradingAgents())
    report = publisher.sync_completed_deep_report(run_id="system-run")
    assert report["body"] == "# Public analysis"
    assert "system-run" not in report.values()

def test_beat_schedules_daily_quick_and_monday_deep_jobs():
    schedule = build_public_research_beat_schedule()
    assert schedule["public-quick-research"]["schedule"].hour == {7}
    assert schedule["public-deep-research"]["schedule"].day_of_week == {1}
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
& ".\.test_deps\Scripts\python.exe" -m pytest backend_api_python/tests/test_public_research_publisher.py backend_api_python/tests/test_celery_boundaries.py -q --basetemp .pytest-public-publisher-red
```

Expected: missing publisher functions or missing `persist_history` argument.

- [ ] **Step 3: Implement isolated public generation**

```python
def analyze(..., user_id: int | None = None, persist_history: bool = True) -> dict[str, Any]:
    # Existing callers retain their current persistence behavior.
    if persist_history:
        memory_id = self._store_analysis_memory(result, user_id=user_id)
        if memory_id:
            result["memory_id"] = memory_id
```

The migration creates a disabled non-login user named `__datavest_public_research__` with a non-usable password hash. The publisher resolves that exact username and fails closed if it does not exist; it must not fall back to user ID 1.

Quick generation calls FastAnalysis with `persist_history=False`, builds an allowlisted result, then completes the matching public record. Deep generation creates a TradingAgents run for the system principal. The sync job fetches only `complete_report.md` from a completed system-owned run, applies a byte limit and control-character cleanup, and saves safe body/title/provenance text without putting `source_run_id` in the payload.

Add:

```python
"public-quick-research": {"task": "datavest.tasks.publish_public_quick_reports", "schedule": crontab(hour=7, minute=15)},
"public-deep-research": {"task": "datavest.tasks.enqueue_public_deep_reports", "schedule": crontab(day_of_week=1, hour=8, minute=0)},
"public-deep-research-sync": {"task": "datavest.tasks.sync_public_deep_reports", "schedule": crontab(minute="*/15")},
```

- [ ] **Step 4: Run publisher, Celery and account regressions**

Run:

```powershell
& ".\.test_deps\Scripts\python.exe" -m pytest backend_api_python/tests/test_public_research_publisher.py backend_api_python/tests/test_celery_boundaries.py backend_api_python/tests/test_ai_assistant_insights.py -q --basetemp .pytest-public-publisher-green
```

Expected: all tests pass and account reports remain account-scoped.

- [ ] **Step 5: Commit**

```powershell
git add backend/backend_api_python/app/services/fast_analysis.py backend/backend_api_python/app/services/smart_insights/public_research_publisher.py backend/backend_api_python/app/tasks/smart_insights.py backend/backend_api_python/app/celery_app.py backend/backend_api_python/migrations/20260913_public_research_reports.sql backend/backend_api_python/tests/test_public_research_publisher.py backend/backend_api_python/tests/test_celery_boundaries.py
git commit -m "feat: schedule public guest research reports"
```

### Task 4: Guest-only read-only Smart Insights UI

**Files:**

- Modify: `frontend/src/api/publicMarketEndpoints.js`
- Modify: `frontend/src/api/smart-insights.js`
- Modify: `frontend/src/views/smart-insights/watchlistOpinions.js`
- Modify: `frontend/src/views/smart-insights/components/AssetOpinionsSection.vue`
- Modify: `frontend/src/views/smart-insights/index.vue`
- Modify: `frontend/src/locales/lang/vi-VN.js`
- Modify: `frontend/src/locales/lang/en-US.js`
- Modify: `frontend/tests/unit/smartInsightsWatchlistOpinions.test.mjs`
- Modify: `frontend/tests/unit/smartInsightsPageContract.test.mjs`

**Interfaces:**

- Consumes: Task 2's public report API.
- Produces: `getPublicResearchReport`, guest row fields `quickReport`, `deepReport`, `canCreateReport: false`, and a guest-safe report viewer.

- [ ] **Step 1: Write failing frontend tests**

```js
test('guest common assets expose read-only public quick and deep reports', () => {
  const rows = buildSharedOpinionRows(commonAssets, opinions, null, publicReports)
  expect(rows.map(row => row.deepReport.kind)).toEqual(['deep', 'deep', 'deep'])
  expect(rows.every(row => row.canCreateReport === false)).toBe(true)
})

test('guest page loads public reports and contains no TradingAgents write call', () => {
  expect(apiSource).toContain('/api/smart-insights/public/reports')
  expect(pageSource).not.toContain('createTradingAgentsRun(')
})
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
Set-Location frontend
pnpm test:unit -- smartInsightsWatchlistOpinions.test.mjs smartInsightsPageContract.test.mjs
```

Expected: guest report fields or API helper are absent.

- [ ] **Step 3: Implement public loading and read-only presentation**

```js
export function getPublicResearchReport (assetKey, reportKind, params = {}) {
  return request({
    url: `${PUBLIC_MARKET_ENDPOINTS.smartInsightsPublicReports}/${encodeURIComponent(assetKey)}/${encodeURIComponent(reportKind)}`,
    method: 'get', params
  })
}
```

When `isGuest`, load the public quick/deep reports for the fixed catalogue only. Guest buttons read `Xem báo cáo nhanh` and `Xem phân tích chuyên sâu`; they open a text-bound modal showing effective date, generated time and public provenance. Do not mount `DeepAnalysisPanel`, use `v-html`, call monitor endpoints, or call any create endpoint for a guest. Logged-in rows retain existing quick/deep behavior and watchlist scope.

- [ ] **Step 4: Run frontend tests and lint**

Run:

```powershell
Set-Location frontend
pnpm test:unit -- smartInsightsWatchlistOpinions.test.mjs smartInsightsPageContract.test.mjs
pnpm exec eslint src/api/smart-insights.js src/views/smart-insights/index.vue src/views/smart-insights/watchlistOpinions.js src/views/smart-insights/components/AssetOpinionsSection.vue
```

Expected: targeted tests and lint pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/api/publicMarketEndpoints.js frontend/src/api/smart-insights.js frontend/src/views/smart-insights/watchlistOpinions.js frontend/src/views/smart-insights/components/AssetOpinionsSection.vue frontend/src/views/smart-insights/index.vue frontend/src/locales/lang/vi-VN.js frontend/src/locales/lang/en-US.js frontend/tests/unit/smartInsightsWatchlistOpinions.test.mjs frontend/tests/unit/smartInsightsPageContract.test.mjs
git commit -m "feat: let guests view public asset research"
```

### Task 5: Current-period backfill and release verification

**Files:**

- Create: `backend/backend_api_python/app/commands/backfill_public_research.py`
- Modify: `backend/backend_api_python/tests/test_public_research_publisher.py`
- Modify: `deploy/vps/configure_env.py`

**Interfaces:**

- Consumes: Task 3 publisher functions.
- Produces: `python -m app.commands.backfill_public_research --quick --deep`.

- [ ] **Step 1: Write the failing command test**

```python
def test_backfill_queues_current_quick_and_deep_sets(monkeypatch):
    calls = []
    monkeypatch.setattr(backfill_public_research, "publish_daily_public_quick_reports", lambda: calls.append("quick"))
    monkeypatch.setattr(backfill_public_research, "enqueue_weekly_public_deep_reports", lambda: calls.append("deep"))
    assert backfill_public_research.main(["--quick", "--deep"]) == 0
    assert calls == ["quick", "deep"]
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
& ".\.test_deps\Scripts\python.exe" -m pytest backend_api_python/tests/test_public_research_publisher.py -q --basetemp .pytest-public-backfill-red
```

Expected: the command module is absent.

- [ ] **Step 3: Implement backfill and safe config checks**

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--deep", action="store_true")
    args = parser.parse_args(argv)
    if not args.quick and not args.deep:
        return 2
    if args.quick:
        publish_daily_public_quick_reports()
    if args.deep:
        enqueue_weekly_public_deep_reports()
    return 0
```

`configure_env.py` validates configuration behavior without logging any credential. The command uses the same publisher path as Beat and does not create account-watchlist records.

- [ ] **Step 4: Run final relevant verification**

Run:

```powershell
& ".\.test_deps\Scripts\python.exe" -m pytest backend_api_python/tests/test_public_research_reports.py backend_api_python/tests/test_public_research_publisher.py backend_api_python/tests/test_smart_insights_mvp_scope.py backend_api_python/tests/test_celery_boundaries.py backend_api_python/tests/test_ai_assistant_insights.py -q --basetemp .pytest-public-research-final
Set-Location frontend
pnpm test:unit
pnpm build
```

Expected: backend scope/publisher tests, frontend suite, and production build pass.

- [ ] **Step 5: Verify the deployed HTTP boundary after backfill**

Run:

```powershell
Invoke-WebRequest "https://datavest.vn/api/smart-insights/public/reports/crypto%3ABTC%2FUSDT/quick?lang=vi-VN" -UseBasicParsing
Invoke-WebRequest "https://datavest.vn/api/smart-insights/public/reports/crypto%3AETH%2FUSDT/quick?lang=vi-VN" -UseBasicParsing
```

Expected: BTC is `200` with no private keys; ETH is `404`.

- [ ] **Step 6: Commit**

```powershell
git add backend/backend_api_python/app/commands/backfill_public_research.py backend/backend_api_python/tests/test_public_research_publisher.py deploy/vps/configure_env.py
git commit -m "feat: add public research backfill command"
```
