# Smart Insights Watchlist and Market Pulse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify the Smart Insights page, display eight source-backed live assets, restrict Asset Opinions to the AI Assistant watchlist, and render seven complete Market Pulse tabs without BTC/Kronos forecasting.

**Architecture:** Add one authenticated backend read endpoint that batches the existing quote service for a server-owned public asset catalog. Keep watchlist ownership in the existing market API, join watchlist rows to briefing opinions through pure frontend helpers, and split the current Smart Insights Vue monolith into focused Live Data Sources, Asset Opinions and Market Pulse components. Existing observation tables and collectors remain unchanged.

**Tech Stack:** Flask, PostgreSQL, pytest, Vue 2.7, Ant Design Vue, native SVG charts, Node test runner, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-29-smart-insights-watchlist-market-pulse-design.md`

## Global Constraints

- Remove the local `legacy-header` and rendered `portfolio-changes` card.
- Do not expose a BTC Forecast, Kronos, `btcBottom`, or forecast placeholder tab.
- Live assets are exactly BTC, ETH, SOL, XRP, LINK, VNINDEX, VN30 and XAU in that order.
- Asset Opinions render only assets in `/api/market/watchlist/get`, the same watchlist used by AI Assistant.
- Missing prices, evidence or analysis remain `UNAVAILABLE`, `PARTIAL` or `STALE`; never generate substitute values.
- Only English and Vietnamese UI copy is added.
- Do not expose provider secrets, environment values or raw exceptions.
- No schema migration and no collector rewrite are required.
- Preserve unrelated dirty work in both repositories.

---

### Task 1: Source-backed live asset endpoint

**Files:**
- Create: `backend_api_python/app/services/smart_insights/live_assets.py`
- Modify: `backend_api_python/app/routes/smart_insights.py`
- Test: `backend_api_python/tests/test_smart_insights_live_assets.py`

**Interfaces:**
- Consumes: `app.services.market.quotes.get_price_map(watchlist: list, timeout_sec: int) -> list`.
- Produces: `get_live_asset_snapshot(*, quote_fetcher=get_price_map, fetched_at=None) -> dict` and authenticated `GET /api/smart-insights/live-assets`.
- Response: `{fetchedAt: str, assets: LiveAssetRow[]}` where each row contains `displaySymbol`, `market`, `symbol`, `price`, `change`, `changePercent`, `source`, `sourceExchangeId`, `sourceMarketType`, `cached`, `stale`, `status`.

- [ ] **Step 1: Write the failing service tests**

```python
from app.services.smart_insights.live_assets import (
    LIVE_ASSET_CATALOG,
    get_live_asset_snapshot,
)


def test_live_asset_catalog_has_the_exact_product_order():
    assert [item["displaySymbol"] for item in LIVE_ASSET_CATALOG] == [
        "BTC", "ETH", "SOL", "XRP", "LINK", "VNINDEX", "VN30", "XAU"
    ]
    assert LIVE_ASSET_CATALOG[-1] == {
        "displaySymbol": "XAU", "market": "Forex", "symbol": "XAUUSD"
    }


def test_live_asset_snapshot_preserves_unavailable_and_stale_truth():
    def fetcher(items, timeout_sec):
        assert timeout_sec == 12
        assert items == list(LIVE_ASSET_CATALOG)
        return [
            {
                "market": "Crypto", "symbol": "BTC/USDT", "price": 77000,
                "change": 100, "changePercent": 0.13, "source": "ticker",
            },
            {
                "market": "Forex", "symbol": "XAUUSD", "price": 4500,
                "change": -10, "changePercent": -0.22, "source": "ticker",
                "cached": True, "stale": True,
            },
        ]
    result = get_live_asset_snapshot(
        quote_fetcher=fetcher,
        fetched_at="2026-08-29T00:00:00+00:00",
    )
    by_symbol = {row["displaySymbol"]: row for row in result["assets"]}
    assert by_symbol["BTC"]["status"] == "LIVE"
    assert by_symbol["XAU"]["status"] == "STALE"
    assert by_symbol["ETH"]["status"] == "UNAVAILABLE"
    assert by_symbol["ETH"]["price"] == 0
```

- [ ] **Step 2: Run the service tests and verify RED**

Run from `backend_api_python`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_smart_insights_live_assets.py -q
```

Expected: collection fails because `app.services.smart_insights.live_assets` does not exist.

- [ ] **Step 3: Implement the catalog and normalizer**

```python
from datetime import datetime, timezone

from app.services.market.quotes import get_price_map

LIVE_ASSET_CATALOG = (
    {"displaySymbol": "BTC", "market": "Crypto", "symbol": "BTC/USDT"},
    {"displaySymbol": "ETH", "market": "Crypto", "symbol": "ETH/USDT"},
    {"displaySymbol": "SOL", "market": "Crypto", "symbol": "SOL/USDT"},
    {"displaySymbol": "XRP", "market": "Crypto", "symbol": "XRP/USDT"},
    {"displaySymbol": "LINK", "market": "Crypto", "symbol": "LINK/USDT"},
    {"displaySymbol": "VNINDEX", "market": "VNStock", "symbol": "VNINDEX"},
    {"displaySymbol": "VN30", "market": "VNStock", "symbol": "VN30"},
    {"displaySymbol": "XAU", "market": "Forex", "symbol": "XAUUSD"},
)


def get_live_asset_snapshot(*, quote_fetcher=get_price_map, fetched_at=None):
    observed_at = fetched_at or datetime.now(timezone.utc).isoformat()
    quotes = quote_fetcher(list(LIVE_ASSET_CATALOG), timeout_sec=12)
    indexed = {(row.get("market"), row.get("symbol")): row for row in quotes}
    assets = []
    for item in LIVE_ASSET_CATALOG:
        quote = indexed.get((item["market"], item["symbol"]), {})
        price = float(quote.get("price") or 0)
        stale = bool(quote.get("stale"))
        assets.append({
            **item,
            "price": price,
            "change": float(quote.get("change") or 0),
            "changePercent": float(quote.get("changePercent") or 0),
            "source": str(quote.get("source") or ""),
            "sourceExchangeId": str(quote.get("source_exchange_id") or ""),
            "sourceMarketType": str(quote.get("source_market_type") or ""),
            "cached": bool(quote.get("cached")),
            "stale": stale,
            "status": "STALE" if price > 0 and stale else "LIVE" if price > 0 else "UNAVAILABLE",
        })
    return {"fetchedAt": observed_at, "assets": assets}
```

- [ ] **Step 4: Add the authenticated route and route tests**

Add to `app/routes/smart_insights.py`:

```python
@smart_insights_blp.route("/live-assets", methods=["GET"])
@observe_feature_operation("smart_insights", "live_assets")
@login_required
def live_assets():
    try:
        from app.services.smart_insights.live_assets import get_live_asset_snapshot
        return _ok(get_live_asset_snapshot())
    except Exception:
        logger.exception("smart insights live assets failed")
        return _fail("smart_insights_live_assets_unavailable", 503)
```

Route tests must assert unauthenticated `401`, authenticated `200`, exact asset order, and that a patched service exception returns the bounded `503` message without the exception text.

- [ ] **Step 5: Run focused backend tests and verify GREEN**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_smart_insights_live_assets.py tests\test_smart_insights_foundation.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1 only**

```powershell
git add backend_api_python/app/services/smart_insights/live_assets.py backend_api_python/app/routes/smart_insights.py backend_api_python/tests/test_smart_insights_live_assets.py
git commit -m "feat: add Smart Insights live asset feed"
```

---

### Task 2: Watchlist-only Asset Opinion model

**Files:**
- Create: `src/views/smart-insights/watchlistOpinions.js`
- Test: `tests/unit/smartInsightsWatchlistOpinions.test.mjs`

**Interfaces:**
- Consumes: watchlist rows `{market, symbol, name}` and overview opinions `{symbol, market, ...}`.
- Produces: `buildWatchlistOpinionRows(watchlist, opinions) -> OpinionRow[]` with `watchlistItem`, `opinion`, `analysisStatus` and canonical identity.

- [ ] **Step 1: Write failing watchlist join tests**

```javascript
import assert from 'node:assert/strict'
import test from 'node:test'
import { buildWatchlistOpinionRows } from '../../src/views/smart-insights/watchlistOpinions.js'

test('renders only watchlist assets in watchlist order', () => {
  const rows = buildWatchlistOpinionRows(
    [
      { market: 'Crypto', symbol: 'ETH/USDT', name: 'Ethereum' },
      { market: 'VNStock', symbol: 'FPT', name: 'FPT' }
    ],
    [
      { market: 'crypto', symbol: 'BTC', stance: 'POSITIVE' },
      { market: 'crypto', symbol: 'ETH', stance: 'NEUTRAL' },
      { market: 'vn', symbol: 'FPT', stance: 'POSITIVE' }
    ]
  )
  assert.deepEqual(rows.map(row => row.symbol), ['ETH/USDT', 'FPT'])
  assert.equal(rows[0].opinion.stance, 'NEUTRAL')
  assert.equal(rows[1].opinion.stance, 'POSITIVE')
})

test('keeps a watchlist row when analysis is unavailable', () => {
  const [row] = buildWatchlistOpinionRows(
    [{ market: 'Forex', symbol: 'XAUUSD', name: 'Gold' }],
    []
  )
  assert.equal(row.analysisStatus, 'UNAVAILABLE')
  assert.equal(row.opinion, null)
})
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
node --test tests\unit\smartInsightsWatchlistOpinions.test.mjs
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement canonical identity and the watchlist join**

Implement exported functions:

```javascript
export function canonicalOpinionSymbol (value) {
  const symbol = String(value || '').trim().toUpperCase()
  if (symbol === 'XAUUSD' || symbol === 'GOLD') return 'XAU'
  return symbol.replace(/[/:-](USDT|USD)$/u, '')
}

export function canonicalOpinionMarket (value) {
  return ({ Crypto: 'crypto', VNStock: 'vn', USStock: 'us', Forex: 'gold' })[value] || String(value || '').toLowerCase()
}

export function buildWatchlistOpinionRows (watchlist = [], opinions = []) {
  const indexed = new Map(opinions.map(opinion => [
    `${canonicalOpinionMarket(opinion.market)}:${canonicalOpinionSymbol(opinion.symbol)}`,
    opinion
  ]))
  return watchlist.map(item => {
    const key = `${canonicalOpinionMarket(item.market)}:${canonicalOpinionSymbol(item.symbol)}`
    const opinion = indexed.get(key) || null
    return {
      id: key,
      symbol: item.symbol,
      displaySymbol: canonicalOpinionSymbol(item.symbol),
      market: item.market,
      name: item.name || item.symbol,
      watchlistItem: item,
      opinion,
      analysisStatus: opinion ? 'AVAILABLE' : 'UNAVAILABLE'
    }
  })
}
```

- [ ] **Step 4: Run the join tests and verify GREEN**

```powershell
node --test tests\unit\smartInsightsWatchlistOpinions.test.mjs
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2 only in QuantDinger-Vue**

```powershell
git add src/views/smart-insights/watchlistOpinions.js tests/unit/smartInsightsWatchlistOpinions.test.mjs
git commit -m "feat: scope Smart Insights opinions to watchlist"
```

---

### Task 3: Live Data Sources component and refresh lifecycle

**Files:**
- Create: `src/views/smart-insights/liveAssets.js`
- Create: `src/views/smart-insights/components/LiveDataSources.vue`
- Modify: `src/api/smart-insights.js`
- Test: `tests/unit/smartInsightsLiveAssets.test.mjs`

**Interfaces:**
- Consumes: `getSmartInsightsLiveAssets() -> {data: {fetchedAt, assets}}`.
- Produces: `normalizeLiveAssetRows(payload)`, `formatLiveAssetPrice(value)`, and component event `refresh`.

- [ ] **Step 1: Write failing response normalization tests**

```javascript
import assert from 'node:assert/strict'
import test from 'node:test'
import { LIVE_ASSET_ORDER, normalizeLiveAssetRows } from '../../src/views/smart-insights/liveAssets.js'

test('normalizes the exact live asset order without inventing missing prices', () => {
  const rows = normalizeLiveAssetRows({
    fetchedAt: '2026-08-29T00:00:00Z',
    assets: [{ displaySymbol: 'BTC', price: 77000, changePercent: 1, status: 'LIVE' }]
  })
  assert.deepEqual(rows.map(row => row.displaySymbol), LIVE_ASSET_ORDER)
  assert.equal(rows[0].price, 77000)
  assert.equal(rows[1].price, null)
  assert.equal(rows[1].status, 'UNAVAILABLE')
})
```

- [ ] **Step 2: Run the test and verify RED**

```powershell
node --test tests\unit\smartInsightsLiveAssets.test.mjs
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement the frontend normalizer and API call**

`LIVE_ASSET_ORDER` must equal:

```javascript
export const LIVE_ASSET_ORDER = ['BTC', 'ETH', 'SOL', 'XRP', 'LINK', 'VNINDEX', 'VN30', 'XAU']
```

`normalizeLiveAssetRows` indexes server rows by `displaySymbol`, returns all eight rows in order, converts only finite positive prices to numbers, and marks absent rows `UNAVAILABLE`.

Add to `src/api/smart-insights.js`:

```javascript
export function getSmartInsightsLiveAssets () {
  return request({ url: '/api/smart-insights/live-assets', method: 'get' })
}
```

- [ ] **Step 4: Build `LiveDataSources.vue`**

The component accepts `rows`, `fetchedAt`, `loading` and `error`. It renders one horizontally scrollable chip per asset with price, signed percentage, source and LIVE/STALE/UNAVAILABLE badge. It contains no timer and no provider fetch; page lifecycle owns refresh scheduling.

- [ ] **Step 5: Add lifecycle contract assertions**

Extend `smartInsightsLiveAssets.test.mjs` to read `index.vue` and assert that it contains `LIVE_ASSET_REFRESH_MS = 30000`, calls `window.setInterval`, calls `window.clearInterval`, and renders `<live-data-sources` before `<main class="legacy-main">`.

- [ ] **Step 6: Run tests and lint the touched files**

```powershell
node --test tests\unit\smartInsightsLiveAssets.test.mjs
npx eslint src/views/smart-insights/liveAssets.js src/views/smart-insights/components/LiveDataSources.vue src/api/smart-insights.js
```

Expected: tests and lint pass without fixes.

- [ ] **Step 7: Commit Task 3 only in QuantDinger-Vue**

```powershell
git add src/views/smart-insights/liveAssets.js src/views/smart-insights/components/LiveDataSources.vue src/api/smart-insights.js tests/unit/smartInsightsLiveAssets.test.mjs
git commit -m "feat: add Smart Insights live data strip"
```

---

### Task 4: Seven-tab Market Pulse model and charts

**Files:**
- Create: `src/views/smart-insights/marketPulse.js`
- Create: `src/views/smart-insights/components/PulseTrendChart.vue`
- Create: `src/views/smart-insights/components/MarketPulseSection.vue`
- Test: `tests/unit/smartInsightsMarketPulse.test.mjs`

**Interfaces:**
- Consumes: existing `/api/smart-insights/crypto-market-pulse` payload with `tabs.overview`, `tabs.flows`, `tabs.sentimentDerivatives`, `tabs.cycle`, `tabs.onchain`, and `tabs.whales`.
- Produces: `MARKET_PULSE_TABS`, `buildPulsePanel(pulse, key)`, `normalizePulseSeries(series)`, plus selected-tab event from `MarketPulseSection.vue`.

- [ ] **Step 1: Write failing tab and series tests**

```javascript
import assert from 'node:assert/strict'
import test from 'node:test'
import { MARKET_PULSE_TABS, buildPulsePanel, normalizePulseSeries } from '../../src/views/smart-insights/marketPulse.js'

test('exposes seven evidence-backed tabs and no forecast surface', () => {
  assert.deepEqual(MARKET_PULSE_TABS.map(tab => tab.key), [
    'overview', 'flows', 'sentiment', 'derivatives', 'cycle', 'onchain', 'whales'
  ])
  assert.equal(JSON.stringify(MARKET_PULSE_TABS).match(/forecast|kronos|btcBottom/iu), null)
})

test('splits sentiment and derivative metrics from the shared backend tab', () => {
  const pulse = { tabs: { sentimentDerivatives: { metrics: [
    { metric: 'crypto.fear_greed.index', value: 60 },
    { metric: 'crypto.derivatives.funding_rate', value: 0.01 }
  ] } } }
  assert.deepEqual(buildPulsePanel(pulse, 'sentiment').metrics.map(row => row.metric), ['crypto.fear_greed.index'])
  assert.deepEqual(buildPulsePanel(pulse, 'derivatives').metrics.map(row => row.metric), ['crypto.derivatives.funding_rate'])
})

test('keeps one valid chart point visible', () => {
  assert.deepEqual(normalizePulseSeries([{ effectiveAt: '2026-08-29', value: 10 }]), [
    { effectiveAt: '2026-08-29', value: 10, metric: '', symbol: '' }
  ])
})
```

- [ ] **Step 2: Run the tests and verify RED**

```powershell
node --test tests\unit\smartInsightsMarketPulse.test.mjs
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement the pure Market Pulse model**

`MARKET_PULSE_TABS` contains Vietnamese and English labels. `buildPulsePanel` maps overview, flows, cycle, onchain and whales directly; sentiment and derivatives map to `sentimentDerivatives` and filter metrics using `/fear|greed|sentiment/iu` versus `/derivative|funding|margin|liquidation|open[_ ]?interest/iu`. `normalizePulseSeries` rejects non-finite values, sorts by `effectiveAt`, and preserves one-point series.

- [ ] **Step 4: Implement `PulseTrendChart.vue`**

Render a responsive native SVG with:

- a zero reference line when the numeric domain crosses zero;
- one `<circle>` for a one-point series;
- a `<polyline>` and endpoint dot for two or more points;
- latest numeric value and effective date;
- explicit unavailable copy for an empty series.

The component receives only `{series, title, unit, status}` and performs no API calls.

- [ ] **Step 5: Implement `MarketPulseSection.vue`**

Render the seven tabs, three source/coverage summary cards, and tab-specific panels:

- overview: Fear & Greed and ETF history;
- flows: ETF summaries plus flow series;
- sentiment: Fear & Greed and sentiment metrics;
- derivatives, cycle, onchain, whales: metric cards and grouped `PulseTrendChart` instances.

Do not read `tabs.btcBottom`. Evidence buttons emit `open-evidence` only when `evidenceId` exists.

- [ ] **Step 6: Add static component assertions and verify GREEN**

The test reads `MarketPulseSection.vue` and asserts all seven keys are consumed, `PulseTrendChart` is used, and `/forecast|kronos|btcBottom/iu` does not match the component source.

```powershell
node --test tests\unit\smartInsightsMarketPulse.test.mjs
npx eslint src/views/smart-insights/marketPulse.js src/views/smart-insights/components/PulseTrendChart.vue src/views/smart-insights/components/MarketPulseSection.vue
```

- [ ] **Step 7: Commit Task 4 only in QuantDinger-Vue**

```powershell
git add src/views/smart-insights/marketPulse.js src/views/smart-insights/components/PulseTrendChart.vue src/views/smart-insights/components/MarketPulseSection.vue tests/unit/smartInsightsMarketPulse.test.mjs
git commit -m "feat: complete Smart Insights market pulse charts"
```

---

### Task 5: Integrate the simplified Smart Insights page

**Files:**
- Create: `src/views/smart-insights/components/AssetOpinionsSection.vue`
- Modify: `src/views/smart-insights/index.vue`
- Modify: `src/locales/lang/en-US.js`
- Modify: `src/locales/lang/vi-VN.js`
- Test: `tests/unit/smartInsightsPageContract.test.mjs`

**Interfaces:**
- Consumes: `getWatchlist`, `getSmartInsightsLiveAssets`, `buildWatchlistOpinionRows`, `LiveDataSources`, `AssetOpinionsSection`, and `MarketPulseSection`.
- Produces: final Smart Insights page behavior and 30-second live-asset refresh lifecycle.

- [ ] **Step 1: Write failing page contract tests**

```javascript
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')

test('removes duplicate legacy surfaces', () => {
  assert.doesNotMatch(source, /<header class="legacy-header"/u)
  assert.doesNotMatch(source, /class="legacy-card portfolio-changes"/u)
})

test('uses the AI Assistant watchlist for opinions', () => {
  assert.match(source, /getWatchlist/u)
  assert.match(source, /buildWatchlistOpinionRows/u)
  assert.match(source, /\/ai-asset-analysis/u)
})

test('has no BTC forecast or Kronos surface', () => {
  assert.doesNotMatch(source, /forecast|kronos|btcBottom/iu)
})
```

- [ ] **Step 2: Run the page contract and verify RED**

```powershell
node --test tests\unit\smartInsightsPageContract.test.mjs
```

Expected: duplicate legacy surfaces still match.

- [ ] **Step 3: Build `AssetOpinionsSection.vue`**

Move opinion table markup out of `index.vue`. Accept `rows`, `loading` and `error`; render only rows supplied by `buildWatchlistOpinionRows`. Missing analysis displays localized `UNAVAILABLE` copy. Empty rows display a router link to `/ai-asset-analysis`. Evidence actions emit `open-evidence`; no add/remove editor is implemented here.

- [ ] **Step 4: Refactor `index.vue`**

Delete local legacy header, portfolio change markup/computed property and obsolete CSS. Add independent state fields:

```javascript
liveAssets: [],
liveAssetsFetchedAt: '',
liveAssetsLoading: false,
liveAssetsError: '',
watchlist: [],
watchlistLoading: false,
watchlistError: '',
liveAssetsRefreshTimer: null
```

At module scope define `const LIVE_ASSET_REFRESH_MS = 30000`. `mounted` loads overview/pulse/health, watchlist and live assets independently and starts one interval. `beforeDestroy` clears it. `opinionRows` calls `buildWatchlistOpinionRows(this.watchlist, this.overview?.opinions || [])`.

Replace the in-page ticker with `<live-data-sources>` immediately before `<main class="legacy-main">`; render `<asset-opinions-section>` and `<market-pulse-section>` in the main content.

- [ ] **Step 5: Add English and Vietnamese copy**

Add keys for live status, stale cache, unavailable quote, manage watchlist in AI Assistant, analysis pending, each of the seven tab labels, latest value and observed time. Do not add forecast/Kronos copy.

- [ ] **Step 6: Run focused frontend tests and lint**

```powershell
node --test tests\unit\smartInsightsWatchlistOpinions.test.mjs tests\unit\smartInsightsLiveAssets.test.mjs tests\unit\smartInsightsMarketPulse.test.mjs tests\unit\smartInsightsPageContract.test.mjs tests\unit\smartInsightsModules.test.mjs
npx eslint src/views/smart-insights/index.vue src/views/smart-insights/components/AssetOpinionsSection.vue src/locales/lang/en-US.js src/locales/lang/vi-VN.js
```

Expected: all focused tests and lint pass.

- [ ] **Step 7: Commit Task 5 only in QuantDinger-Vue**

```powershell
git add src/views/smart-insights/index.vue src/views/smart-insights/components/AssetOpinionsSection.vue src/locales/lang/en-US.js src/locales/lang/vi-VN.js tests/unit/smartInsightsPageContract.test.mjs
git commit -m "refactor: simplify Smart Insights workspace"
```

---

### Task 6: Regression, Docker and browser acceptance

**Files:**
- Modify only if a verification defect is reproduced by a new failing test.

**Interfaces:**
- Consumes: completed backend endpoint and frontend page.
- Produces: verified local runtime at `http://127.0.0.1:8888/` and backend at `http://127.0.0.1:5001/`.

- [ ] **Step 1: Run complete backend verification**

```powershell
.\.venv\Scripts\python.exe -m compileall -q app scripts
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings -p no:cacheprovider
```

Expected: compile exits `0`; all existing and new tests pass.

- [ ] **Step 2: Run complete frontend verification**

```powershell
npm run test:unit
npm run lint:nofix
npm run build
```

Expected: unit tests, lint and production build pass.

- [ ] **Step 3: Check patch integrity in both repositories**

```powershell
git diff --check
```

Expected: no whitespace errors; line-ending notices are informational only.

- [ ] **Step 4: Rebuild and recreate local Compose**

From the backend worktree:

```powershell
& "C:\Users\ASUS\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe" compose -f docker-compose.yml -f docker-compose.datavest.yml build backend frontend
& "C:\Users\ASUS\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe" compose -f docker-compose.yml -f docker-compose.datavest.yml up -d --force-recreate
& "C:\Users\ASUS\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe" compose -f docker-compose.yml -f docker-compose.datavest.yml ps --all
```

Expected: migration exits `0`; backend, frontend, PostgreSQL, both Redis services, scheduler and Celery services are healthy.

- [ ] **Step 5: Run authenticated HTTP smoke without printing tokens**

Generate a short-lived JWT inside `datavest-backend`, call `/api/smart-insights/live-assets`, `/overview`, `/crypto-market-pulse`, and `/api/market/watchlist/get` with the Flask test client, and print only status codes, asset symbols, watchlist count and pulse tab statuses.

Expected: all responses are `200`; live asset symbols match the exact eight-item catalog; overview/pulse retain LIVE/DEMO truth.

- [ ] **Step 6: Verify browser behavior**

Open `http://127.0.0.1:8888/`, authenticate through an existing authorized session, then verify:

- no nested legacy header;
- Live Data Sources is directly beneath the app header;
- all eight live assets show price or an explicit unavailable state;
- Asset Opinions equals the AI Assistant watchlist and no extra imported opinion appears;
- empty watchlist provides the AI Assistant route action;
- seven tabs render distinct panels and charts;
- no forecast, Kronos or portfolio-change card exists;
- English/Vietnamese, light/dark and mobile widths remain usable.

- [ ] **Step 7: Record final evidence and keep worktrees**

Report exact test totals, service health, endpoint counts and browser findings. Preserve both repositories/worktrees; do not merge, push or remove them without a separate user choice.
