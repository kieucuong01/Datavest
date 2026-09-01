# Smart Insights Derivatives Terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a source-labelled, daily crypto derivatives terminal for BTC, ETH, and SOL with complete initial backfill where a provider permits it.

**Architecture:** Provider-specific collectors produce normal Smart Insights `Observation` records and preserve venue identity plus coverage metadata. The crypto pulse adds a dedicated derivatives payload, and a Vue/ECharts terminal renders positioning, carry, options, and stress context without fake history.

**Tech Stack:** Flask/Python, PostgreSQL observations, Celery Beat, Vue 2, Ant Design Vue, ECharts, pytest, Node test runner.

**Spec:** `docs/superpowers/specs/2026-08-31-smart-insights-derivatives-terminal-design.md`

## Global Constraints

- Use official public APIs for core data; Browser Use is limited to existing CoinGlass context sources.
- Preserve provider identity in every point, card, chart legend, and tooltip.
- Use daily UTC points; BTC/ETH/SOL receive futures data, BTC/ETH only receive options.
- Never replace unavailable data with zero.
- Daily import is 00:40 UTC; retry failed derivative sources at 02:15 UTC; reconcile seven days.
- Derivatives are evidence-only, never investment or leverage instructions.
- Do not use `grid-column: 1 / -1`.

---

### Task 1: Define contracts and sources

**Files:**
- Create: `backend/backend_api_python/app/services/smart_insights/derivatives.py`
- Modify: `backend/backend_api_python/app/services/smart_insights/sources.py`
- Test: `backend/backend_api_python/tests/test_smart_insights_derivatives.py`

**Interfaces:**
- Produces `DerivativeCoverage`, `DerivativeBackfillRequest`, `daily_effective_at(as_of)`, and metric constants.
- Registers `bybit-derivatives`, `binance-usdm-derivatives`, and `deribit-public-derivatives`.

- [ ] **Step 1: Write failing tests**

```python
def test_daily_effective_at_is_previous_utc_day():
    assert daily_effective_at(datetime(2026, 8, 31, 0, 40, tzinfo=UTC)) == datetime(2026, 8, 30, tzinfo=UTC)

def test_coverage_retains_window_limit():
    item = DerivativeCoverage("binance-usdm-derivatives", OI_USD, "BTC", START, END, True)
    assert item.as_dict()["historyLimited"] is True
```

- [ ] **Step 2: Verify RED**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_derivatives.py -q`

Expected: import failure because the contract module is absent.

- [ ] **Step 3: Implement minimal contract**

```python
@dataclass(frozen=True)
class DerivativeCoverage:
    source: str; metric: str; symbol: str; start: datetime; end: datetime; history_limited: bool
    def as_dict(self) -> dict[str, object]:
        return {"source": self.source, "metric": self.metric, "symbol": self.symbol, "start": self.start.isoformat(), "end": self.end.isoformat(), "historyLimited": self.history_limited}
```

Register the three sources with official URLs, `crypto` market, `daily` cadence, and distinct methodology versions.

- [ ] **Step 4: Verify GREEN**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_derivatives.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/backend_api_python/app/services/smart_insights/derivatives.py backend/backend_api_python/app/services/smart_insights/sources.py backend/backend_api_python/tests/test_smart_insights_derivatives.py
git commit -m "feat: define derivatives insight contracts"
```

### Task 2: Bybit historical positioning

**Files:**
- Create: `backend/backend_api_python/app/services/smart_insights/bybit_derivatives.py`
- Modify: `backend/backend_api_python/app/services/smart_insights/collectors.py`
- Test: `backend/backend_api_python/tests/test_smart_insights_bybit_derivatives.py`

**Interfaces:**
- Produces `BybitDerivativesCollector.collect_daily(as_of)` and `.backfill(request)`.
- Emits BTC/ETH/SOL funding, OI, long/short account ratio, and price with source `bybit-derivatives`.

- [ ] **Step 1: Write failing pagination and invalid-value tests**

```python
def test_backfill_walks_cursor_and_emits_daily_utc_oi():
    rows = BybitDerivativesCollector(client=FakeBybit([PAGE_ONE, PAGE_TWO])).backfill(REQUEST)
    assert [row.effective_at for row in rows] == [DAY_ONE, DAY_TWO]

def test_missing_value_is_not_emitted_as_zero():
    with pytest.raises(BybitDerivativesUnavailable, match="SCHEMA_DRIFT"):
        BybitDerivativesCollector(client=FakeBybit([[{"openInterest": None}]])).backfill(REQUEST)
```

- [ ] **Step 2: Verify RED**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_bybit_derivatives.py -q`

Expected: import failure because the collector is absent.

- [ ] **Step 3: Implement collector**

Implement a bounded public client for `/v5/market/open-interest`, `/v5/market/account-ratio`, `/v5/market/funding/history`, and daily kline data. Use cursor/page continuation, validate numeric fields, record actual coverage, and register the source in `default_collector_registry`.

- [ ] **Step 4: Verify GREEN**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_bybit_derivatives.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/backend_api_python/app/services/smart_insights/bybit_derivatives.py backend/backend_api_python/app/services/smart_insights/collectors.py backend/backend_api_python/tests/test_smart_insights_bybit_derivatives.py
git commit -m "feat: collect Bybit derivatives history"
```

### Task 3: Binance USD-M windowed data

**Files:**
- Create: `backend/backend_api_python/app/services/smart_insights/binance_usdm_derivatives.py`
- Modify: `backend/backend_api_python/app/services/smart_insights/collectors.py`
- Test: `backend/backend_api_python/tests/test_smart_insights_binance_usdm_derivatives.py`

**Interfaces:**
- Produces `BinanceUsdmDerivativesCollector.collect_daily(as_of)` and `.backfill(request)`.
- Emits funding, OI USD, taker imbalance, basis, and window-limited coverage.

- [ ] **Step 1: Write failing history-limit and annualization tests**

```python
def test_oi_backfill_is_clamped_to_30_days():
    result = BinanceUsdmDerivativesCollector(FakeBinance()).backfill(REQUEST_365_DAYS)
    assert result.coverage.history_limited is True
    assert result.coverage.start == REQUEST_365_DAYS.end - timedelta(days=30)

def test_funding_is_annualized_from_8_hour_interval():
    assert annualize_funding(Decimal("0.0001"), hours=8) == Decimal("0.1095")
```

- [ ] **Step 2: Verify RED**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_binance_usdm_derivatives.py -q`

Expected: import failure because collector helpers are absent.

- [ ] **Step 3: Implement collector**

Use only public funding, OI history, taker buy/sell, basis, and continuous-kline endpoints. Clamp OI/taker/basis requests to 30 days, annotate `historyLimited`, and never call top-trader endpoints that require a key.

- [ ] **Step 4: Verify GREEN**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_binance_usdm_derivatives.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/backend_api_python/app/services/smart_insights/binance_usdm_derivatives.py backend/backend_api_python/app/services/smart_insights/collectors.py backend/backend_api_python/tests/test_smart_insights_binance_usdm_derivatives.py
git commit -m "feat: collect Binance USD-M derivatives"
```

### Task 4: Direct Deribit futures and options

**Files:**
- Create: `backend/backend_api_python/app/services/smart_insights/deribit_public_derivatives.py`
- Modify: `backend/backend_api_python/app/services/smart_insights/collectors.py`
- Test: `backend/backend_api_python/tests/test_smart_insights_deribit_public_derivatives.py`

**Interfaces:**
- Produces `DeribitPublicDerivativesCollector.collect_daily(as_of)` and `.backfill(request)` for BTC/ETH.
- Emits basis/curve, perpetual price/volume, put/call OI, and historical volatility.

- [ ] **Step 1: Write failing options integrity tests**

```python
def test_daily_collection_calculates_put_call_ratio():
    rows = DeribitPublicDerivativesCollector(FakeDeribit(OPTION_CHAIN)).collect_daily(NOW)
    assert metric_value(rows, PUT_CALL_OI_RATIO, "BTC") == Decimal("0.8")

def test_one_sided_options_fails_closed():
    with pytest.raises(DeribitPublicDerivativesUnavailable, match="OPTIONS_COVERAGE_INCOMPLETE"):
        DeribitPublicDerivativesCollector(FakeDeribit(CALLS_ONLY)).collect_daily(NOW)
```

- [ ] **Step 2: Verify RED**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_deribit_public_derivatives.py -q`

Expected: import failure because direct collector is absent.

- [ ] **Step 3: Implement collector**

Use direct JSON-RPC `get_book_summary_by_currency` and `get_historical_volatility`. Aggregate call/put OI only with complete two-sided coverage; validate futures curve expiries; leave `openbb-deribit` unchanged as fallback.

- [ ] **Step 4: Verify GREEN**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_deribit_public_derivatives.py backend/backend_api_python/tests/test_smart_insights_openbb_deribit.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/backend_api_python/app/services/smart_insights/deribit_public_derivatives.py backend/backend_api_python/app/services/smart_insights/collectors.py backend/backend_api_python/tests/test_smart_insights_deribit_public_derivatives.py
git commit -m "feat: collect direct Deribit derivatives"
```

### Task 5: Backfill command and daily schedule

**Files:**
- Create: `backend/backend_api_python/app/commands/backfill_derivatives.py`
- Modify: `backend/backend_api_python/app/tasks/smart_insights.py`
- Modify: `backend/backend_api_python/app/celery_app.py`
- Test: `backend/backend_api_python/tests/test_smart_insights_derivatives_schedule.py`

**Interfaces:**
- Produces `python -m app.commands.backfill_derivatives --sources ... --start ... --end ...`.
- Produces `enqueue_derivatives_daily_import()` and failed-source-only retry.

- [ ] **Step 1: Write failing schedule tests**

```python
def test_daily_import_runs_at_0040_utc():
    assert celery_app.conf.beat_schedule["crypto-derivatives-daily-import"]["schedule"] == crontab(hour=0, minute=40)

def test_retry_filters_non_derivative_sources():
    assert retry_derivative_source_codes(["bybit-derivatives", "fred"]) == ("bybit-derivatives",)
```

- [ ] **Step 2: Verify RED**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_derivatives_schedule.py -q`

Expected: import failure because the task/schedule is absent.

- [ ] **Step 3: Implement command and schedules**

Create a command that submits source-bounded refresh requests, supports `--dry-run`, and reports coverage. Register daily `crontab(hour=0, minute=40)` plus retry `crontab(hour=2, minute=15)`; retry reads only failed derivative source codes from the prior run.

- [ ] **Step 4: Verify GREEN**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_derivatives_schedule.py backend/backend_api_python/tests/test_celery_boundaries.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/backend_api_python/app/commands/backfill_derivatives.py backend/backend_api_python/app/tasks/smart_insights.py backend/backend_api_python/app/celery_app.py backend/backend_api_python/tests/test_smart_insights_derivatives_schedule.py
git commit -m "feat: schedule derivatives imports"
```

### Task 6: Dedicated API payload

**Files:**
- Modify: `backend/backend_api_python/app/services/smart_insights/crypto_pulse.py`
- Modify: `backend/backend_api_python/app/services/smart_insights/snapshot_pipeline.py`
- Test: `backend/backend_api_python/tests/test_smart_insights_crypto_pulse.py`

**Interfaces:**
- Produces `tabs.sentimentDerivatives.derivatives = {status, assets, coverage, series, latest, stress}`.
- Preserves existing generic `metrics` and `series`.

- [ ] **Step 1: Write failing response-shape test**

```python
def test_pulse_exposes_source_labelled_derivatives(repository):
    terminal = build_crypto_pulse(repository)["tabs"]["sentimentDerivatives"]["derivatives"]
    assert terminal["latest"][0]["source"] == "bybit-derivatives"
    assert terminal["coverage"][0]["historyLimited"] is False
```

- [ ] **Step 2: Verify RED**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_crypto_pulse.py -q`

Expected: assertion failure because the dedicated payload is absent.

- [ ] **Step 3: Implement payload shaper**

```python
def _derivatives_terminal(rows):
    return {"status": _status(rows), "assets": ["BTC", "ETH", "SOL"], "coverage": _coverage(rows), "series": _series(rows), "latest": _latest(rows), "stress": _stress(rows)}
```

- [ ] **Step 4: Verify GREEN**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_crypto_pulse.py backend/backend_api_python/tests/test_smart_insights_derivatives.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/backend_api_python/app/services/smart_insights/crypto_pulse.py backend/backend_api_python/app/services/smart_insights/snapshot_pipeline.py backend/backend_api_python/tests/test_smart_insights_crypto_pulse.py
git commit -m "feat: expose derivatives terminal payload"
```

### Task 7: Vue/ECharts terminal

**Files:**
- Create: `frontend/src/views/smart-insights/components/DerivativesTerminal.vue`
- Modify: `frontend/src/views/smart-insights/components/MarketPulseSection.vue`
- Modify: `frontend/src/views/smart-insights/marketPulse.js`
- Test: `frontend/tests/unit/smartInsightsModules.test.mjs`

**Interfaces:**
- Consumes `panel.derivatives`.
- Produces asset/range controls, chart view models, provider badges, coverage states, and accessible tooltips.

- [ ] **Step 1: Write failing frontend module tests**

```js
test('derivatives keeps venue series separate', () => {
  const panel = buildPulsePanel(FIXTURE, 'derivatives')
  assert.equal(panel.derivatives.seriesGroups.length, 2)
  assert.notEqual(panel.derivatives.seriesGroups[0].source, panel.derivatives.seriesGroups[1].source)
})

test('SOL options is not applicable rather than zero', () => {
  assert.equal(buildDerivativeOptionsState('SOL', FIXTURE), 'NOT_APPLICABLE')
})
```

- [ ] **Step 2: Verify RED**

Run: `node --test frontend/tests/unit/smartInsightsModules.test.mjs`

Expected: import or assertion failure because derivatives terminal helpers are absent.

- [ ] **Step 3: Implement terminal**

Route `activeKey === 'derivatives'` to `<derivatives-terminal :derivatives="panel.derivatives" :locale="locale" />` and exclude it from generic cards/charts. Build the full-width price/OI combo and funding zero-line charts with ECharts, plus BTC/ETH carry/options and secondary CoinGlass snapshot cards.

- [ ] **Step 4: Verify GREEN**

Run: `node --test frontend/tests/unit/smartInsightsModules.test.mjs`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/smart-insights/components/DerivativesTerminal.vue frontend/src/views/smart-insights/components/MarketPulseSection.vue frontend/src/views/smart-insights/marketPulse.js frontend/tests/unit/smartInsightsModules.test.mjs
git commit -m "feat: add derivatives terminal UI"
```

### Task 8: Verification and local snapshot

**Files:**
- Modify only scoped files if fresh verification identifies a defect.

- [ ] **Step 1: Run focused backend suite**

Run: `pytest backend/backend_api_python/tests/test_smart_insights_derivatives.py backend/backend_api_python/tests/test_smart_insights_bybit_derivatives.py backend/backend_api_python/tests/test_smart_insights_binance_usdm_derivatives.py backend/backend_api_python/tests/test_smart_insights_deribit_public_derivatives.py backend/backend_api_python/tests/test_smart_insights_derivatives_schedule.py backend/backend_api_python/tests/test_smart_insights_crypto_pulse.py -q`

Expected: PASS.

- [ ] **Step 2: Run frontend unit verification**

Run: `node --test frontend/tests/unit/smartInsightsModules.test.mjs`

Expected: PASS.

- [ ] **Step 3: Run first local backfill**

```bash
python -m app.commands.backfill_derivatives --sources bybit-derivatives,binance-usdm-derivatives,deribit-public-derivatives --start 2025-08-31 --end 2026-08-31 --dry-run
python -m app.commands.backfill_derivatives --sources bybit-derivatives,binance-usdm-derivatives,deribit-public-derivatives --start 2025-08-31 --end 2026-08-31
```

Expected: per-source coverage/record output and no zero-fill warning.

- [ ] **Step 4: Build and inspect local UI**

Run: `docker build --no-cache -t datavest-frontend:local -f frontend/Dockerfile frontend`

Recreate only the frontend in the established three-compose-file stack. Open `http://localhost:8888`, choose Phái sinh, verify BTC/ETH/SOL toggles and chart tooltips, and capture a screenshot.

- [ ] **Step 5: Inspect the final scoped diff**

Run: `git diff -- backend/backend_api_python/app/services/smart_insights frontend/src/views/smart-insights frontend/tests/unit/smartInsightsModules.test.mjs`

Expected: only the collector, scheduling, pulse payload, and derivatives terminal changes described by Tasks 1-7; preserve unrelated worktree changes.

## Self-review

- Tasks 1-4 implement every provider contract and collector; Task 5 implements initial/daily/retry operations; Task 6 preserves API compatibility; Task 7 creates the terminal; Task 8 proves data, tests, build, and browser behavior.
- The plan uses the same `DerivativeBackfillRequest`, `DerivativeCoverage`, `panel.derivatives`, and source codes in every task.
- No task asks for a paid API, an undocumented aggregate, synthetic history, or generic placeholder work.
