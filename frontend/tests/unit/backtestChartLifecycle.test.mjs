import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const componentPath = fileURLToPath(
  new URL('../../src/views/backtest-center/index.vue', import.meta.url)
)
const source = fs.readFileSync(componentPath, 'utf8')
const portfolioResultPath = fileURLToPath(
  new URL('../../src/views/backtest-center/PortfolioResult.vue', import.meta.url)
)
const portfolioResultSource = fs.readFileSync(portfolioResultPath, 'utf8')

test('backtest center compiles a source manifest before accepting runtime controls', () => {
  assert.match(source, /compileScriptSource\(\{ sourceId \}\)/)
  assert.match(source, /this\.manifest = compiled\.data && compiled\.data\.manifest/)
  assert.match(source, /return Boolean\(this\.manifest && this\.manifest\.leverageAllowed\)/)
})

test('backtest center submits only the Strategy API V2 request contract', () => {
  assert.match(source, /runStrategyBacktest\(\{[\s\S]*?sourceId: this\.form\.sourceId[\s\S]*?startDate:[\s\S]*?endDate:[\s\S]*?params: this\.params/)
  assert.doesNotMatch(source, /strategy_config|script_params|strict_mode|strategy_code/)
})

test('closed trades expose lifecycle, prices, wallet equity, and profit tone', () => {
  for (const field of ['entry_time', 'exit_time', 'entry_price', 'exit_price', 'balance']) {
    assert.match(source, new RegExp(`dataIndex: '${field}'`))
  }
  assert.match(source, /dataIndex: 'profit'[\s\S]*?profitTone\(value\)/)
  assert.match(source, /number > 0\) return 'positive'/)
  assert.match(source, /number < 0\) return 'negative'/)
})

test('backtest workbench keeps execution controls visible and moves history into a drawer', () => {
  assert.match(source, /class="run-action-bar"/)
  assert.match(source, /class="config-scroll"/)
  assert.match(source, /<a-drawer[\s\S]*?backtest-history-drawer/)
  assert.match(source, /v-for="item in history"/)
  assert.doesNotMatch(source, /class="panel history-panel"/)
})

test('saved backtest details expose an in-drawer loading state', () => {
  assert.match(source, /v-if="historyDetailLoading" class="drawer-detail-loading"/)
  assert.match(source, /this\.historyDetailLoading = true/)
  assert.match(source, /this\.historyVisible = false[\s\S]*?finally/)
  assert.match(source, /strategyV2\.backtest\.historyLoading/)
})

test('CTA source summary exposes the concrete instrument instead of only its count', () => {
  assert.match(source, /this\.manifest\.strategyType === 'cta' && instruments\.length/)
  assert.match(source, /instruments\.map\(this\.formatInstrument\)\.join\(', '\)/)
  assert.match(source, /marketContext\.\$\{marketType\}/)
})

test('portfolio drawdown chart uses initial capital and backend drawdown points', () => {
  assert.match(portfolioResultSource, /const base = this\.initialCapital > 0/)
  assert.match(portfolioResultSource, /const savedDrawdown = Number\(item\.drawdown\)/)
  assert.match(portfolioResultSource, /item\.drawdown !== undefined/)
  assert.match(portfolioResultSource, /strategyV2\.backtest\.maxDrawdownHint/)
})

test('trade review centers the full entry-to-exit range and draws after data is ready', () => {
  assert.match(portfolioResultSource, /@load="renderReviewMarkers"/)
  assert.match(portfolioResultSource, /Math\.ceil\(tradeBars \* 1\.2\)/)
  assert.match(portfolioResultSource, /chart\.scrollByDistance\(-Math\.max/)
})
