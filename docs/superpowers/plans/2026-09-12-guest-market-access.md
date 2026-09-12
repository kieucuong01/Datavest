# DataVest Guest Market Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let anonymous visitors use source-backed Smart Insights and a read-only indicator chart while preserving server-side authentication for all personal, AI, authoring, alert, portfolio, optimizer, and strategy actions.

**Architecture:** Add an explicit frontend route-access contract and install a guest route inventory into the existing Vue shell. Add dedicated read-only Smart Insights and calendar HTTP routes backed by shared LIVE data and fixed BTC/VNINDEX/XAU scope; keep all tenant APIs unchanged. Route `/indicator-ide` through an entry component that renders either the existing authenticated IDE or a new guest-only chart built on the already-public K-line endpoint and client-side built-in indicators.

**Tech Stack:** Vue 2.7, Vue Router 3, Vuex, Ant Design Vue, klinecharts, Flask, pytest, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-12-guest-market-access-design.md`

## Global Constraints

- Public Smart Insights asset scope is exactly BTC, VNINDEX, and XAU.
- Public services must never read tenant watchlists, AI history, monitor state, portfolios, prompts, or production-account imports.
- Existing private endpoints and their `@login_required`/`@admin_required` decorators remain unchanged.
- Guest chart never accepts or executes user-provided Python code.
- Missing data stays missing; no fabricated zero, opinion, or freshness value.
- Preserve unrelated dirty work and do not modify Graphify artifacts.
- No new dependency and no CORS or token-format change.

---

### Task 1: Public Smart Insights service and routes

**Files:**
- Create: `backend/backend_api_python/app/services/smart_insights/public_access.py`
- Modify: `backend/backend_api_python/app/routes/smart_insights.py`
- Test: `backend/backend_api_python/tests/test_smart_insights_guest_access.py`

**Interfaces:**
- Produces: `PUBLIC_ASSET_SCOPE`, `PublicSmartInsightsService`, and `get_public_smart_insights_service()`.
- Produces HTTP GET routes under `/api/smart-insights/public/{overview,dates,evidence/<id>,data-health,live-assets,crypto-market-pulse}`.
- Consumes the existing `SmartInsightsService`, `SmartInsightsRepository`, response compaction helpers, and live-asset snapshot loader.

- [ ] **Step 1: Write failing service tests**

```python
def test_public_overview_uses_only_fixed_shared_scope_and_no_tenant_import():
    service = PublicSmartInsightsService(repository=RepositoryDouble())
    result = service.get_overview(as_of="2026-09-12", locale="vi-VN")
    assert [item["displaySymbol"] for item in result["assets"]] == ["BTC", "VNINDEX", "XAU"]
    assert RepositoryDouble.production_import_calls == []

def test_public_evidence_returns_only_allowlisted_fields():
    result = PublicSmartInsightsService(repository=EvidenceRepository()).get_evidence("obs-1")
    assert set(result) <= PUBLIC_EVIDENCE_FIELDS
    assert "user_id" not in result
    assert "request_json" not in result
```

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m pytest tests/test_smart_insights_guest_access.py -q --basetemp=.pytest-tmp-guest-access-red`

Expected: import failure because `public_access.py` does not exist.

- [ ] **Step 3: Implement the bounded public service**

```python
PUBLIC_ASSET_SCOPE = (
    {"market": "Crypto", "symbol": "BTC/USDT", "displaySymbol": "BTC"},
    {"market": "VNStock", "symbol": "VNINDEX", "displaySymbol": "VNINDEX"},
    {"market": "Forex", "symbol": "XAUUSD", "displaySymbol": "XAU"},
)

class PublicSmartInsightsService:
    def __init__(self, repository=None):
        self.repository = repository or SmartInsightsRepository()
        self.service = SmartInsightsService(
            repository=self.repository,
            watchlist_loader=lambda _user_id: [dict(item) for item in PUBLIC_ASSET_SCOPE],
        )

    def get_overview(self, *, as_of=None, locale="vi-VN"):
        result = self.service.get_overview(
            user_id=0, as_of=as_of, market="all", mode="live"
        )
        result["assets"] = [dict(item) for item in PUBLIC_ASSET_SCOPE]
        result["scope"] = "PUBLIC_COMMON_ASSETS"
        return result
```

Call repository-backed shared methods directly for pulse, dates, evidence, and health so user `0` cannot resolve production imports. Sanitize evidence and health rows with explicit field sets.

- [ ] **Step 4: Add failing anonymous route tests**

```python
def test_public_routes_are_anonymous_but_private_routes_still_require_jwt(client):
    assert client.get("/api/smart-insights/public/overview").status_code == 200
    assert client.get("/api/smart-insights/public/crypto-market-pulse").status_code == 200
    assert client.get("/api/smart-insights/overview").status_code == 401
    assert client.post("/api/smart-insights/refresh", json={}).status_code == 401
```

- [ ] **Step 5: Implement public GET handlers without auth decorators**

Handlers validate `as_of`, `compact`, and evidence ID through the public service, use existing `_ok`/`_fail`, and return generic 503 messages on unexpected errors. Do not alter private handlers.

- [ ] **Step 6: Run scoped backend tests and verify GREEN**

Run: `python -m pytest tests/test_smart_insights_guest_access.py tests/test_smart_insights_foundation.py -q --basetemp=.pytest-tmp-guest-smart-green`

Expected: all selected tests pass.

### Task 2: Public economic calendar boundary

**Files:**
- Modify: `backend/backend_api_python/app/routes/global_market.py`
- Test: `backend/backend_api_python/tests/test_smart_insights_guest_access.py`

**Interfaces:**
- Produces: `GET /api/global-market/public/calendar`.
- Consumes: existing cached calendar loaders and data-contract formatter.

- [ ] **Step 1: Write failing anonymous calendar tests**

```python
def test_public_calendar_is_anonymous_and_rejects_force_refresh(client):
    assert client.get("/api/global-market/public/calendar").status_code == 200
    response = client.get("/api/global-market/public/calendar?force=1")
    assert response.status_code == 400
    assert client.get("/api/global-market/calendar").status_code == 401
```

- [ ] **Step 2: Run the test and verify RED**

Run the calendar test by node ID and confirm the public route returns 404.

- [ ] **Step 3: Extract a shared read helper and add the public route**

```python
def _economic_calendar_response(*, allow_force: bool):
    force = request.args.get("force", "").lower() in ("true", "1")
    if force and not allow_force:
        return jsonify({"code": 0, "msg": "force_refresh_requires_auth", "data": []}), 400
    source = request.args.get("source", "")
    if source not in {"", "investing_browser", "akshare_wallstreetcn"}:
        return jsonify({"code": 0, "msg": "Unsupported calendar source", "data": []}), 400
    return _load_calendar_payload(source=source, force=force)

@global_market_blp.route("/public/calendar", methods=["GET"])
def public_economic_calendar():
    return _economic_calendar_response(allow_force=False)
```

Keep `/calendar` authenticated and call the same helper with `allow_force=True`.

- [ ] **Step 4: Run the scoped test and verify GREEN**

Run: `python -m pytest tests/test_smart_insights_guest_access.py -q --basetemp=.pytest-tmp-guest-calendar-green`

Expected: all tests pass.

### Task 3: Frontend route-access contract and guest shell

**Files:**
- Create: `frontend/src/router/access.js`
- Modify: `frontend/src/config/router.config.js`
- Modify: `frontend/src/router/generator-routers.js`
- Modify: `frontend/src/store/modules/async-router.js`
- Modify: `frontend/src/permission.js`
- Test: `frontend/tests/unit/guestRouteAccess.test.mjs`

**Interfaces:**
- Produces: `isPublicPath(path)`, `requiresAuthentication(route)`, `buildGuestRoutes(routes)`, and Vuex action `GenerateGuestRoutes`.
- Consumes route `meta.access` values `public` and `authenticated`.

- [ ] **Step 1: Write failing route-policy tests**

```javascript
test('guest routes keep public entries and visibly lock private entries', () => {
  const routes = buildGuestRoutes(fixtureRoutes)
  assert.equal(findRoute(routes, '/smart-insights').meta.guestLocked, false)
  assert.equal(findRoute(routes, '/indicator-ide').meta.guestLocked, false)
  assert.equal(findRoute(routes, '/ai-asset-analysis').meta.guestLocked, true)
  assert.equal(findRoute(routes, '/strategy-ide').meta.icon, 'lock')
})

test('public path matching does not make private descendants public', () => {
  assert.equal(isPublicPath('/smart-insights'), true)
  assert.equal(isPublicPath('/indicator-ide'), true)
  assert.equal(isPublicPath('/strategy-ide'), false)
  assert.equal(isPublicPath('/portfolio'), false)
})
```

- [ ] **Step 2: Run and verify RED**

Run: `node --test tests/unit/guestRouteAccess.test.mjs`

Expected: module-not-found for `src/router/access.js`.

- [ ] **Step 3: Implement route access helpers and route metadata**

Set `meta.access: 'public'` on Smart Insights and Indicator; set `authenticated` on AI Assistant, portfolio, optimizer, Strategy IDE, backtest, universe, profile, and admin entries. Clone routes rather than mutating `asyncRouterMap`; replace a protected guest entry icon with `lock` and retain the original as `featureIcon`.

- [ ] **Step 4: Install guest routes in Vuex and global guard**

When no token, install guest routes once before entering a public URL. Protected URLs redirect to login with `to.fullPath`. On invalid token, logout then remain on a public route by installing guest routes; otherwise redirect to login. Change the authenticated login fallback to `/smart-insights`.

- [ ] **Step 5: Run route tests and verify GREEN**

Run: `node --test tests/unit/guestRouteAccess.test.mjs`

Expected: all tests pass.

### Task 4: Guest header and login gate

**Files:**
- Create: `frontend/src/utils/guestAccess.js`
- Modify: `frontend/src/components/GlobalHeader/RightContent.vue`
- Modify: `frontend/src/layouts/BasicLayout.vue`
- Modify: `frontend/src/locales/lang/vi-VN.js`
- Modify: `frontend/src/locales/lang/en-US.js`
- Test: `frontend/tests/unit/guestAccessUi.test.mjs`

**Interfaces:**
- Produces: `hasAccessToken()`, `loginTarget(fullPath)`, guest header login action, and protected-navigation login handling.
- Consumes `ACCESS_TOKEN` and Vue Router.

- [ ] **Step 1: Write failing auth-state and return-path tests**

```javascript
test('login target preserves the complete protected destination', () => {
  assert.deepEqual(loginTarget('/strategy-ide?tab=script'), {
    path: '/user/login', query: { redirect: '/strategy-ide?tab=script' }
  })
})
```

- [ ] **Step 2: Run and verify RED**

Run: `node --test tests/unit/guestAccessUi.test.mjs`

Expected: module-not-found for `src/utils/guestAccess.js`.

- [ ] **Step 3: Implement guest header state**

`RightContent` renders avatar and notices only when authenticated; guests receive a keyboard-focusable primary `Đăng nhập` button while language and theme controls remain available.

- [ ] **Step 4: Add layout-level guest mode**

Pass guest state to top navigation, keep locked entries visible, and prevent guest live-asset polling from invoking a private URL by switching the API client in Task 5. Add localized guest/login/locked copy.

- [ ] **Step 5: Run UI helper tests and verify GREEN**

Run: `node --test tests/unit/guestAccessUi.test.mjs`

Expected: all tests pass.

### Task 5: Public Smart Insights frontend experience

**Files:**
- Modify: `frontend/src/api/smart-insights.js`
- Modify: `frontend/src/api/global-market.js`
- Modify: `frontend/src/views/smart-insights/index.vue`
- Modify: `frontend/src/views/smart-insights/components/AssetOpinionsSection.vue`
- Modify: `frontend/src/locales/smart-insights.js`
- Modify: `frontend/tests/unit/smartInsightsLifecycle.test.mjs`
- Test: `frontend/tests/unit/smartInsightsGuestMode.test.mjs`

**Interfaces:**
- Consumes the public HTTP routes from Tasks 1 and 2.
- Produces an anonymous Smart Insights page with fixed common assets and no private API calls.

- [ ] **Step 1: Write failing API and page behavior tests**

```javascript
test('Smart Insights API client uses only public read endpoints', async () => {
  const calls = []
  const record = options => { calls.push(options.url); return Promise.resolve({ data: {} }) }
  await createSmartInsightsApi(record).overview()
  await createSmartInsightsApi(record).pulse()
  await createGlobalMarketApi(record).calendar()
  assert.deepEqual(calls, [
    '/api/smart-insights/public/overview',
    '/api/smart-insights/public/crypto-market-pulse',
    '/api/global-market/public/calendar'
  ])
})

test('guest overview assets replace personal watchlist loading', async () => {
  const page = createPage({ overview: { assets: commonAssets, opinions: [] } })
  await page.loadAll()
  assert.deepEqual(page.watchlist.map(item => item.displaySymbol), ['BTC', 'VNINDEX', 'XAU'])
  assert.equal(privateWatchlistCalls, 0)
})
```

- [ ] **Step 2: Run and verify RED**

Run: `node --test tests/unit/smartInsightsGuestMode.test.mjs tests/unit/smartInsightsLifecycle.test.mjs`

Expected: public URL and no-watchlist assertions fail.

- [ ] **Step 3: Switch API clients and page loading**

Remove `getWatchlist()` from the Smart Insights lifecycle. Populate rows from `overview.assets`; retain all existing concurrent loading, cache, stale-response, and retry behavior. Live assets and calendar use public URLs.

- [ ] **Step 4: Add guest presentation and action gates**

Show the guest/common-data banner. `AssetOpinionsSection` receives `guest`; it removes manage-watchlist copy, retains shared report details, and emits login actions for AI/deep analysis. Guest detail does not call `getAnalysisHistory` or mount `DeepAnalysisPanel`.

- [ ] **Step 5: Run Smart Insights tests and verify GREEN**

Run: `node --test tests/unit/smartInsightsGuestMode.test.mjs tests/unit/smartInsightsLifecycle.test.mjs tests/unit/smartInsightsModules.test.mjs`

Expected: all selected tests pass.

### Task 6: Read-only guest indicator chart

**Files:**
- Create: `frontend/src/views/indicator-entry/index.vue`
- Create: `frontend/src/views/indicator-guest/index.vue`
- Create: `frontend/src/views/indicator-guest/guestIndicatorState.js`
- Modify: `frontend/src/config/router.config.js`
- Modify: `frontend/src/locales/lang/vi-VN.js`
- Modify: `frontend/src/locales/lang/en-US.js`
- Test: `frontend/tests/unit/guestIndicatorChart.test.mjs`

**Interfaces:**
- Consumes `KlineChart`, `hasAccessToken()`, and the existing authenticated `IndicatorIDE`.
- Produces the same `/indicator-ide` route with guest/authenticated view selection.

- [ ] **Step 1: Write failing guest chart state tests**

```javascript
test('guest chart supports only public asset and indicator presets', () => {
  assert.deepEqual(GUEST_ASSETS.map(item => item.displaySymbol), ['BTC', 'VNINDEX', 'XAU'])
  assert.equal(toggleIndicator([], 'ema')[0].id, 'ema')
  assert.deepEqual(toggleIndicator([{ id: 'ema' }], 'ema'), [])
  assert.throws(() => normalizeGuestAsset('AAPL'), /unsupported_asset/)
})
```

- [ ] **Step 2: Run and verify RED**

Run: `node --test tests/unit/guestIndicatorChart.test.mjs`

Expected: module-not-found for `guestIndicatorState.js`.

- [ ] **Step 3: Implement pure guest state and chart page**

Render controls for BTC/VNINDEX/XAU, timeframe, and built-in indicators. Pass only preset indicators into `KlineChart`; show source/freshness area and a login CTA for strategy creation. Do not import or call private indicator APIs.

- [ ] **Step 4: Implement authenticated/guest entry component**

```vue
<template>
  <indicator-ide v-if="authenticated" />
  <guest-indicator-chart v-else />
</template>
```

Point the `/indicator-ide` route to this entry component.

- [ ] **Step 5: Run guest chart tests and verify GREEN**

Run: `node --test tests/unit/guestIndicatorChart.test.mjs`

Expected: all tests pass.

### Task 7: Regression, security, build, and browser verification

**Files:**
- Modify only if a failing test exposes a task-scoped defect.

**Interfaces:**
- Consumes all preceding deliverables.
- Produces verification evidence; no new feature contract.

- [ ] **Step 1: Run backend access-control regression tests**

Run from `backend/backend_api_python`:

`python -m pytest tests/test_smart_insights_guest_access.py tests/test_smart_insights_foundation.py tests/test_auth_security.py tests/test_indicator_signal_alerts.py tests/test_strategy_v2_routes.py -q --basetemp=.pytest-tmp-guest-final`

- [ ] **Step 2: Run frontend guest and existing navigation tests**

Run from `frontend`:

`node --test tests/unit/guestRouteAccess.test.mjs tests/unit/guestAccessUi.test.mjs tests/unit/smartInsightsGuestMode.test.mjs tests/unit/guestIndicatorChart.test.mjs tests/unit/smartInsightsLifecycle.test.mjs tests/unit/headerNavigationContract.test.mjs`

- [ ] **Step 3: Run frontend build and lint changed files**

Run: `pnpm run build`

Run ESLint against the changed JS/Vue files without `--fix`.

- [ ] **Step 4: Run security checks**

Confirm anonymous private endpoints return 401, public payloads contain no forbidden fields, no public handler accepts arbitrary code/user ID/force refresh, and `git diff --cached` contains no secret-like values.

- [ ] **Step 5: Verify in a real browser**

At desktop and mobile widths, verify anonymous `/smart-insights` and `/indicator-ide`, the guest header/login button, locked AI/portfolio/strategy routes, redirect preservation, dark/light theme, language switching, chart tooltip/indicator controls, and no private endpoint requests in the network log.

- [ ] **Step 6: Review scope and working tree**

Compare changed files against this plan, run `git diff --check`, and ensure unrelated existing modifications and Graphify artifacts were not staged or altered by this task.
