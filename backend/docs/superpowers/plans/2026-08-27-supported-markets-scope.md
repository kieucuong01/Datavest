# DataVest Supported Markets Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict DataVest's user-facing product and market-data runtime to US stocks, Vietnamese stocks, Crypto, and Gold/XAU while rejecting every other market explicitly.

**Architecture:** Add one canonical allowlist shared by Flask services and Vue utilities. The allowlist controls catalog output, datasource creation, symbol search, watchlist validation, strategy/universe inputs, and Smart Insights filters; no caller may silently fall back to Crypto. Gold remains the `Forex` provider namespace for compatibility but only canonical symbols `XAUUSD`/`XAU` are accepted. Existing database rows and retired adapter files are preserved until a separate destructive cleanup approval; retired markets are removed from active runtime and UI.

**Tech Stack:** Flask/Python, PostgreSQL-compatible repository layer, Vue 2.7, Jest/Vitest-style Node unit tests, Docker Compose.

**Spec:** User request on 2026-08-27: only US stocks, Vietnamese stocks, Crypto, and gold via XAU; remove all other markets.

## Global Constraints

- Supported market keys are exactly `USStock`, `VNStock`, `Crypto`, and `Forex` where `Forex` means Gold/XAU only.
- Unsupported markets include `CNStock`, `HKStock`, generic FX pairs, `Futures`, and `MOEX`.
- Unknown or retired market input must return an explicit unsupported-market error; it must never default to Crypto.
- No provider key, environment value, raw exception, or credential may be returned to the browser.
- Existing unrelated Smart Insights, authentication, language, and hidden-community changes must remain intact.
- Historical database rows are not deleted in this change; active API responses filter them out and the migration is additive.

---

### Task 1: Establish the canonical market contract

**Files:**
- Create: `backend_api_python/app/utils/supported_markets.py`
- Create: `backend_api_python/tests/test_supported_markets.py`
- Create: `QuantDinger-Vue/src/utils/supportedMarkets.js`
- Create: `QuantDinger-Vue/tests/unit/supportedMarkets.test.mjs`

**Interfaces:**
- Backend produces `SUPPORTED_MARKETS`, `SUPPORTED_MARKET_ORDER`, `normalize_supported_market(value)`, `canonicalize_supported_symbol(market, symbol)`, and `is_supported_market(value)`.
- Frontend produces `SUPPORTED_MARKETS`, `SUPPORTED_MARKET_ORDER`, `normalizeSupportedMarket(value)`, `canonicalizeSupportedSymbol(market, symbol)`, and `isSupportedMarket(value)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_only_product_markets_are_supported():
    from app.utils.supported_markets import SUPPORTED_MARKETS
    assert SUPPORTED_MARKETS == frozenset({"USStock", "VNStock", "Crypto", "Forex"})

def test_gold_is_the_only_forex_instrument():
    from app.utils.supported_markets import canonicalize_supported_symbol
    assert canonicalize_supported_symbol("Forex", "XAU") == "XAUUSD"
    assert canonicalize_supported_symbol("Forex", "XAU/USD") == "XAUUSD"

def test_retired_market_is_rejected_without_crypto_fallback():
    import pytest
    from app.utils.supported_markets import UnsupportedSupportedMarketError, normalize_supported_market
    with pytest.raises(UnsupportedSupportedMarketError):
        normalize_supported_market("Futures")
```

```javascript
test('exposes only the four supported product markets', async () => {
  const { SUPPORTED_MARKET_ORDER } = await import('../../src/utils/supportedMarkets.js')
  expect(SUPPORTED_MARKET_ORDER).toEqual(['USStock', 'VNStock', 'Crypto', 'Forex'])
})

test('canonicalizes gold aliases and rejects other forex pairs', async () => {
  const { canonicalizeSupportedSymbol } = await import('../../src/utils/supportedMarkets.js')
  expect(canonicalizeSupportedSymbol('Forex', 'XAU/USD')).toBe('XAUUSD')
  expect(() => canonicalizeSupportedSymbol('Forex', 'EURUSD')).toThrow()
})
```

- [ ] **Step 2: Run the focused tests and verify expected failures**

Run backend: `backend_api_python/.venv/Scripts/python.exe -m pytest backend_api_python/tests/test_supported_markets.py -q`

Run frontend: `pnpm exec vitest run tests/unit/supportedMarkets.test.mjs` from `QuantDinger-Vue`.

Expected: import/module failures because the new contract files do not exist.

- [ ] **Step 3: Implement the minimal shared contracts**

```python
SUPPORTED_MARKET_ORDER = ("USStock", "VNStock", "Crypto", "Forex")
SUPPORTED_MARKETS = frozenset(SUPPORTED_MARKET_ORDER)
GOLD_SYMBOLS = frozenset({"XAU", "XAUUSD", "XAU/USD", "XAU-USD", "GOLD"})

class UnsupportedSupportedMarketError(ValueError):
    pass

def normalize_supported_market(value):
    raw = str(value or '').strip()
    aliases = {'us': 'USStock', 'usstock': 'USStock', 'vn': 'VNStock', 'vietnam': 'VNStock', 'vnstock': 'VNStock', 'crypto': 'Crypto', 'forex': 'Forex', 'gold': 'Forex', 'xau': 'Forex'}
    market = aliases.get(raw.lower().replace('-', '').replace('_', ''), raw)
    if market not in SUPPORTED_MARKETS:
        raise UnsupportedSupportedMarketError(f"Unsupported market '{raw}'")
    return market

def canonicalize_supported_symbol(market, symbol):
    canonical_market = normalize_supported_market(market)
    value = str(symbol or '').strip().upper().replace(' ', '')
    if canonical_market == 'Forex':
        if value not in GOLD_SYMBOLS:
            raise UnsupportedSupportedMarketError("Only Gold/XAU is supported in the Forex provider namespace")
        return 'XAUUSD'
    if not value:
        raise ValueError('Empty symbol')
    return value
```

Implement the equivalent pure JavaScript functions with the same aliases and error behavior.

- [ ] **Step 4: Run both focused tests and verify they pass**

Expected: all contract tests pass and no other files are changed by the test command.

---

### Task 2: Lock the backend registry and datasource boundary

**Files:**
- Modify: `backend_api_python/app/utils/market_visibility.py`
- Modify: `backend_api_python/app/markets/registry.py`
- Modify: `backend_api_python/app/data_sources/factory.py`
- Modify: `backend_api_python/app/data_sources/forex.py`
- Modify: `backend_api_python/app/services/market_context.py`
- Create: `backend_api_python/tests/test_supported_market_runtime.py`

**Interfaces:**
- `/api/market/types` and `/api/market/modules` expose only the canonical order.
- `DataSourceFactory.normalize_market`, `get_source`, and `get_kline` reject retired/unknown markets with `UnsupportedSupportedMarketError`.
- `ForexDataSource` accepts only `XAU`, `XAUUSD`, or `XAU/USD`, normalized to `XAUUSD`.

- [ ] **Step 1: Write failing runtime tests**

```python
def test_registry_has_only_supported_markets():
    from app.markets.registry import list_market_keys
    assert list_market_keys() == ['USStock', 'VNStock', 'Crypto', 'Forex']

def test_factory_rejects_retired_market_without_defaulting_to_crypto():
    import pytest
    from app.data_sources.factory import DataSourceFactory
    from app.utils.supported_markets import UnsupportedSupportedMarketError
    with pytest.raises(UnsupportedSupportedMarketError):
        DataSourceFactory.get_source('MOEX')

def test_forex_namespace_accepts_gold_only():
    from app.data_sources.forex import normalize_forex_pair_symbol
    assert normalize_forex_pair_symbol('XAU/USD') == 'XAUUSD'
    import pytest
    with pytest.raises(ValueError):
        normalize_forex_pair_symbol('EURUSD')
```

- [ ] **Step 2: Run tests and confirm they fail for the old registry/fallback behavior**

Run: `backend_api_python/.venv/Scripts/python.exe -m pytest backend_api_python/tests/test_supported_market_runtime.py -q`

Expected: registry still includes retired markets and factory still resolves them.

- [ ] **Step 3: Replace the active registry and factory boundary**

Use `SUPPORTED_MARKET_ORDER` for `MARKET_ORDER`, add a `VNStock` module with `asset_class='equity'`, `base_currency='VND'`, and research/backtest/paper features, remove retired module entries from `MARKET_MODULES`, and make `normalize_market` call `normalize_supported_market` with no empty/unknown fallback. `_create_source` must construct only Crypto, USStock, VNStock, and Forex. Add a VNStock-compatible read-only datasource using the existing production-safe VN gateway path if the generic factory currently lacks one; do not route Vietnamese symbols to CNStock.

Change visibility so the allowlist is a hard upper bound: `ENABLED_MARKETS` may reduce the four markets but cannot re-enable retired ones. Update Forex normalization and every call site to reject non-XAU symbols before network access.

- [ ] **Step 4: Run runtime tests plus existing market-context/factory tests**

Run: `backend_api_python/.venv/Scripts/python.exe -m pytest backend_api_python/tests/test_supported_markets.py backend_api_python/tests/test_supported_market_runtime.py backend_api_python/tests -k "market or factory or watchlist" -q`

Expected: supported-market tests pass; any incompatible legacy test must be updated to the new explicit rejection contract, not restored with a fallback.

---

### Task 3: Remove retired markets from API search, watchlist, and symbol catalog

**Files:**
- Modify: `backend_api_python/app/routes/market.py`
- Modify: `backend_api_python/app/services/market/symbol_search.py`
- Modify: `backend_api_python/app/services/market/watchlist.py`
- Modify: `backend_api_python/app/services/symbol_master_sync.py`
- Modify: `backend_api_python/app/services/market/quotes.py`
- Create: `backend_api_python/tests/test_market_scope_api.py`

**Interfaces:**
- `GET /api/market/types` returns exactly four market entries.
- Search/find/add-watchlist reject `CNStock`, `HKStock`, `Futures`, `MOEX`, and non-XAU `Forex` with a deterministic client error or empty search result as appropriate.
- Symbol master sync only publishes USStock, VNStock, Crypto, and Forex/XAU rows.

- [ ] **Step 1: Write failing API/service tests**

```python
def test_market_types_are_restricted(client):
    response = client.get('/api/market/types')
    assert [item['value'] for item in response.get_json()['data']] == ['USStock', 'VNStock', 'Crypto', 'Forex']

def test_watchlist_rejects_hong_kong_stock():
    from app.services.market.watchlist import validate_watchlist_pair
    assert 'Unsupported market' in validate_watchlist_pair('HKStock', '0700')

def test_symbol_search_never_returns_retired_market_rows():
    from app.services.market.symbol_search import dedupe_symbol_results
    assert dedupe_symbol_results([{'market': 'MOEX', 'symbol': 'SBER'}], 20) == []
```

- [ ] **Step 2: Run tests and observe failure against current seven-market behavior**

Run: `backend_api_python/.venv/Scripts/python.exe -m pytest backend_api_python/tests/test_market_scope_api.py -q`

- [ ] **Step 3: Implement hard filtering and explicit validation**

Normalize every incoming market through the shared backend contract before calling seed search, external providers, quote lookup, or watchlist persistence. Replace the seven-market desired order with `['USStock', 'VNStock', 'Crypto', 'Forex']`. Filter legacy cached/seed rows at the boundary rather than deleting unrelated database history. Restrict static Forex seeds to `XAUUSD`, and ensure production import or symbol master code maps Vietnamese rows to `VNStock` and does not keep CN/HK/futures/MOEX rows active.

- [ ] **Step 4: Run focused tests and endpoint smoke checks**

Run: `backend_api_python/.venv/Scripts/python.exe -m pytest backend_api_python/tests/test_market_scope_api.py backend_api_python/tests/test_watchlist*.py -q`.

Smoke: `curl.exe -s http://127.0.0.1:5001/api/market/types` and assert the JSON values are exactly the four supported markets.

---

### Task 4: Align frontend selectors, AI parsing, universes, optimizer, and Smart Insights

**Files:**
- Modify: `QuantDinger-Vue/src/utils/marketModules.js`
- Modify: `QuantDinger-Vue/src/utils/marketContext.js`
- Modify: `QuantDinger-Vue/src/views/universe-manager/index.vue`
- Modify: `QuantDinger-Vue/src/views/strategy-ide/UniverseLibraryModal.vue`
- Modify: `QuantDinger-Vue/src/views/ai-analysis/components/CopilotWorkbench.vue`
- Modify: `QuantDinger-Vue/src/views/ai-asset-analysis/index.vue`
- Modify: `QuantDinger-Vue/src/views/smart-insights/index.vue`
- Modify: `QuantDinger-Vue/src/views/portfolio-optimizer/index.vue` only if it has a local market list
- Create: `QuantDinger-Vue/tests/unit/marketScopeSelectors.test.mjs`

**Interfaces:**
- All selectors use `SUPPORTED_MARKET_ORDER`; no UI selector contains CNStock, HKStock, Futures, MOEX, or generic FX.
- Smart Insights market filters are `all`, `crypto`, `vn`, `us`, and `gold`; `macro` is removed from market selectors unless it is explicitly rendered as non-market context.
- AI parsing recognizes `USStock`, `VNStock`, `Crypto`, and `Forex`/XAU only.

- [ ] **Step 1: Write failing frontend selector tests**

```javascript
test('fallback market options contain only supported markets', async () => {
  const { FALLBACK_MARKET_MODULES } = await import('../../src/utils/marketModules.js')
  expect(FALLBACK_MARKET_MODULES.map(item => item.key)).toEqual(['USStock', 'VNStock', 'Crypto', 'Forex'])
})

test('frontend cannot canonicalize generic FX or retired markets', async () => {
  const { normalizeSupportedMarket, canonicalizeSupportedSymbol } = await import('../../src/utils/supportedMarkets.js')
  expect(() => normalizeSupportedMarket('MOEX')).toThrow()
  expect(() => canonicalizeSupportedSymbol('Forex', 'EURUSD')).toThrow()
})
```

- [ ] **Step 2: Run tests and verify the old fallback/list behavior fails**

Run: `pnpm exec vitest run tests/unit/marketScopeSelectors.test.mjs` from `QuantDinger-Vue`.

- [ ] **Step 3: Replace hardcoded lists and normalize user input**

Use the shared utility in fallback modules, universe filters, strategy-universe creation, Smart Insights filters, AI opportunity labels, and Copilot symbol parsing. Keep Gold displayed as `Gold (XAU)` while sending `Forex:XAUUSD` to the API. Remove Chinese/Hong Kong aliases and examples from AI prompts and user-visible messages. Make stale saved filters fall back to `all` instead of issuing unsupported requests.

- [ ] **Step 4: Run frontend unit tests and inspect compiled references**

Run: `pnpm exec vitest run tests/unit/supportedMarkets.test.mjs tests/unit/marketScopeSelectors.test.mjs tests/unit/supportedLocales.test.mjs`.

Run: `rg -n "CNStock|HKStock|Futures|MOEX|EURUSD|GBPUSD|USDJPY" src/views src/components src/utils` and confirm remaining hits are non-user-facing compatibility text or explicitly retired code paths; active selector/parser/runtime paths must have zero hits.

---

### Task 5: Scope global market/Smart Insights data and retire unsupported runtime paths

**Files:**
- Modify: `backend_api_python/app/services/global_market_data.py`
- Modify: `backend_api_python/app/data_providers/heatmap.py`
- Modify: `backend_api_python/app/data_providers/commodities.py`
- Modify: `backend_api_python/app/services/market_data_collector.py`
- Modify: `backend_api_python/app/services/fast_analysis_scoring.py` and `backend_api_python/app/services/fundamental_data.py` only where they emit active market lists
- Modify: `backend_api_python/app/tools/import_production_account.py`
- Create: `backend_api_python/tests/test_market_scope_data_providers.py`

**Interfaces:**
- Opportunity/radar/heatmap payloads contain only USStock, VNStock, Crypto, and Gold/XAU.
- Gold is sourced as XAU/XAUUSD; silver, generic FX, futures, MOEX, CN, and HK are unavailable rather than mislabeled.
- Production import maps unsupported legacy assets to an auditable skipped/unsupported result; it does not classify commodities as Futures.

- [ ] **Step 1: Write failing provider-scope tests**

```python
def test_heatmap_payload_excludes_retired_markets():
    from app.utils.supported_markets import SUPPORTED_MARKETS
    rows = [{'market': 'USStock'}, {'market': 'CNStock'}, {'market': 'Forex', 'symbol': 'EURUSD'}]
    from app.utils.market_visibility import filter_market_items
    assert filter_market_items(rows, key='market') == [{'market': 'USStock'}]

def test_production_import_does_not_map_gold_to_futures():
    from app.tools.import_production_account import infer_local_market
    assert infer_local_market({'symbol': 'XAUUSD', 'assetClass': 'commodity'}) == 'Forex'
```

- [ ] **Step 2: Run tests and confirm the old provider/import behavior fails**

Run: `backend_api_python/.venv/Scripts/python.exe -m pytest backend_api_python/tests/test_market_scope_data_providers.py -q`.

- [ ] **Step 3: Filter provider outputs and disable retired branches**

Apply the shared market/symbol contract before aggregation and before serialization. Preserve source/provenance fields for supported rows. For unsupported legacy rows, return a structured `unsupported_market` status where the endpoint contract expects status, or skip them where the contract is a list; never synthesize data. Update import accounting so skipped CN/HK/Futures/MOEX/unsupported FX rows are counted and logged without exposing secrets.

- [ ] **Step 4: Run provider tests and a local Smart Insights smoke test**

Run targeted provider/import tests, then call the local Smart Insights overview and verify no unsupported market keys appear in the response. Do not claim live-provider freshness unless the response contains a real provider and checksum.

---

### Task 6: Static dependency audit and removal of unreachable active references

**Files:**
- Audit: `backend_api_python/app/data_sources/{cn_stock,hk_stock,futures,moex}.py`
- Audit: `backend_api_python/app/services/**`, `backend_api_python/app/routes/**`, `QuantDinger-Vue/src/**`, `docker-compose.datavest.yml`
- Delete only files proven unreachable after the active graph audit; otherwise leave them quarantined and disabled.
- Create: `docs/superpowers/audits/2026-08-27-supported-markets-dependency-audit.md`

**Interfaces:**
- The audit records every remaining reference to a retired market and whether it is active, test-only, migration-only, or compatibility-only.
- Compose/workers do not load retired market adapters on startup.

- [ ] **Step 1: Generate the closest available dependency inventory**

Run `rg -n --glob '*.py' --glob '*.js' --glob '*.vue' --glob '*.yml' "CNStock|HKStock|Futures|MOEX|EURUSD|GBPUSD|USDJPY"` over both repositories and inspect imports/route registration. Graphify is not available in the QuantDinger checkout, so the audit uses this static dependency inventory as the closest code-graph workflow.

- [ ] **Step 2: Remove active references and record quarantined code**

Delete retired adapter modules only if no production import, route, worker, test fixture, or migration still imports them. If historical tests or migrations require the file, keep it but mark it inactive and add the reason to the audit. Do not delete database history or old migrations in this task.

- [ ] **Step 3: Verify no startup/runtime path loads retired adapters**

Run import smoke checks, route registry inspection, and `rg` against active frontend/backend paths. Confirm Docker Compose service definitions are unchanged except for any required environment allowlist.

---

### Task 7: Rebuild local services and perform verification

**Files:**
- Modify only the files already listed above and any focused tests needed to preserve the new contract.

- [ ] **Step 1: Run backend regression tests**

Run the focused market/provider tests and the existing Smart Insights/portfolio optimizer tests. Record exact pass/fail counts and fix regressions without restoring unsupported markets.

- [ ] **Step 2: Run frontend regression tests and production build**

Run supported-market, locale, Smart Insights, and existing frontend unit tests, then build the Vue frontend in Docker because local `node_modules` may be incomplete.

- [ ] **Step 3: Rebuild and restart local Compose services**

Use the configured Docker executable to rebuild backend/frontend and recreate backend, worker, scheduler, and frontend services. Do not print environment values.

- [ ] **Step 4: Verify HTTP behavior**

Check `http://127.0.0.1:8888/`, `/api/market/types`, Smart Insights overview, and one supported symbol-search path. Verify retired market requests return explicit rejection/empty results and supported market catalog is exactly four entries.

- [ ] **Step 5: Report exact scope and any intentionally preserved files/data**

State clearly that the product/runtime has four supported markets, which legacy source files/data were retained for safety, and which destructive cleanup would require a separate explicit migration decision.

