# Smart Insights On-chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a source-backed On-chain terminal using existing CoinMetrics and DefiLlama observations without duplicating CBBI or Altcoin Season from Cycle.

**Architecture:** The backend already categorizes CoinMetrics and DefiLlama observation rows as `onchain`; extend its tested read-model contract only where needed to attach a stable group key and enough history. The Vue terminal consumes the existing tab payload and renders only metrics that arrived from persisted LIVE observations. Cycle retains CBBI and Altcoin Season as its dedicated composite/regime view.

**Tech Stack:** Python/Flask Smart Insights read model, PostgreSQL-backed observations, Vue 2, ECharts, Node built-in tests, pytest, ESLint, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-30-smart-insights-onchain-design.md`

## Global Constraints

- Use only existing `coinmetrics-community`, `defillama-stablecoins`, and `defillama-chains` collectors; add no credential, subscription source, or browser crawler.
- Preserve immutable source attribution, units, timestamps, and unavailable states; never synthesize missing values.
- Do not emit recommendations or automated buy/sell signals.
- CBBI and Altcoin Season remain in the Cycle tab; raw MVRV remains On-chain.
- No new URL controlled by a client; retain existing collector validation and bounded fetch behavior.

---

### Task 1: Stabilize and test the On-chain read-model contract

**Files:**
- Modify: `backend/backend_api_python/app/services/smart_insights/crypto_pulse.py`
- Modify: `backend/backend_api_python/tests/test_smart_insights_live_collectors.py`
- Modify: `backend/backend_api_python/tests/test_production_account_smart_insights_view.py`

**Interfaces:**
- Consumes: persisted crypto observation mappings accepted by `build_crypto_market_pulse(rows, mode)`.
- Produces: `tabs.onchain` with `status`, source cards, latest metric cards, history series, and deterministic groups for `valuation`, `network`, `liquidity`, and `protocol`.

- [ ] **Step 1: Write failing backend tests**

```python
def test_crypto_pulse_groups_existing_onchain_metrics_without_cycle_overlap():
    pulse = build_crypto_market_pulse(_onchain_rows(), mode="live")
    assert pulse["tabs"]["onchain"]["status"] == "AVAILABLE"
    assert [item["key"] for item in pulse["tabs"]["onchain"]["groups"]] == [
        "valuation", "network", "liquidity", "protocol",
    ]
    assert all(not item["metric"].startswith("crypto.cycle.") for item in pulse["tabs"]["onchain"]["series"])
```

- [ ] **Step 2: Run the focused test and verify red**

Run: `pytest backend_api_python/tests/test_smart_insights_live_collectors.py backend_api_python/tests/test_production_account_smart_insights_view.py -q`

Expected: the test fails because `tabs.onchain.groups` does not yet exist.

- [ ] **Step 3: Implement the smallest grouping adapter**

```python
def _onchain_group(metric: str) -> str:
    if metric == "crypto.onchain.mvrv":
        return "valuation"
    if metric == "crypto.onchain.active_addresses":
        return "network"
    if metric == "crypto.stablecoin.supply_usd":
        return "liquidity"
    if metric == "crypto.chain.tvl_usd":
        return "protocol"
    return "other"
```

Return only non-empty groups, keep rows and source metadata unchanged, and exclude `crypto.cycle.*` values.

- [ ] **Step 4: Run focused backend tests and verify green**

Run: `pytest backend_api_python/tests/test_smart_insights_live_collectors.py backend_api_python/tests/test_production_account_smart_insights_view.py -q`

Expected: all selected tests pass.

### Task 2: Add the source-backed On-chain terminal

**Files:**
- Create: `frontend/src/views/smart-insights/components/OnchainTerminal.vue`
- Modify: `frontend/src/views/smart-insights/components/MarketPulseSection.vue`
- Modify: `frontend/src/locales/smart-insights.js`
- Modify: `frontend/tests/unit/smartInsightsModules.test.mjs`

**Interfaces:**
- Consumes: `onchain` tab object with `groups`, `metrics`, `series`, and `sources` from Task 1.
- Produces: responsive grouped cards and ECharts line histories with hover tooltips; empty groups do not render.

- [ ] **Step 1: Write a failing frontend contract test**

```js
test('Smart Insights gives source-backed on-chain data its own grouped terminal', () => {
  assert.match(marketPulse, /OnchainTerminal/u)
  assert.match(onchainTerminal, /valuation/u)
  assert.match(onchainTerminal, /network/u)
  assert.match(onchainTerminal, /tooltip:\s*\{/u)
  assert.doesNotMatch(onchainTerminal, /crypto\.cycle\.cbbi/u)
})
```

- [ ] **Step 2: Run the frontend unit test and verify red**

Run: `node --test frontend/tests/unit/smartInsightsModules.test.mjs`

Expected: the test fails because `OnchainTerminal.vue` is missing.

- [ ] **Step 3: Implement the minimal terminal**

Create a Vue component that maps only known metric codes to group labels and caveats, uses real source series, uses 90D/1Y/ALL controls, and renders `No validated history imported` when no observations arrive. Mount it in `MarketPulseSection` only when `activeKey === 'onchain'`.

- [ ] **Step 4: Run frontend test and scoped lint**

Run: `node --test frontend/tests/unit/smartInsightsModules.test.mjs && npx eslint src/views/smart-insights/components/OnchainTerminal.vue src/views/smart-insights/components/MarketPulseSection.vue src/locales/smart-insights.js --no-fix`

Expected: all tests and scoped lint pass.

### Task 3: Integrate locally and verify data/runtime boundaries

**Files:**
- Modify: `design-qa.md` only to record what was verified and any browser-QA limitation.

**Interfaces:**
- Consumes: built frontend image and existing local Compose stack.
- Produces: a running local Smart Insights On-chain tab with source-backed data when observations are present.

- [ ] **Step 1: Build the frontend image**

Run: `docker compose -f backend/docker-compose.yml -f backend/docker-compose.datavest.yml -f backend/docker-compose.production.yml -f backend/docker-compose.calendar.yml build frontend`

- [ ] **Step 2: Recreate only the frontend service**

Run: `docker compose -f backend/docker-compose.yml -f backend/docker-compose.datavest.yml -f backend/docker-compose.production.yml -f backend/docker-compose.calendar.yml up -d --no-build --force-recreate frontend`

- [ ] **Step 3: Verify runtime health and contracts**

Run: `Invoke-WebRequest http://localhost:8888` and `Invoke-WebRequest http://localhost:5000/api/health`.

Expected: both return HTTP 200 and `datavest-frontend` reports healthy.

- [ ] **Step 4: Verify only proven data appears**

Inspect the Smart Insights response and local browser. Confirm On-chain either shows the persisted source-backed rows with their source labels or the explicit unavailable state. Confirm Cycle still renders CBBI and Altcoin Season and does not receive raw On-chain groups.
