import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { resolveIndicatorStrategyContext } from '../../src/utils/indicatorStrategyContext.js'

const indicatorIdePath = fileURLToPath(
  new URL('../../src/views/indicator-ide/index.vue', import.meta.url)
)
const klineChartPath = fileURLToPath(
  new URL('../../src/views/indicator-analysis/components/KlineChart.vue', import.meta.url)
)
const strategyIdePath = fileURLToPath(
  new URL('../../src/views/strategy-ide/index.vue', import.meta.url)
)
const indicatorIdeSource = fs.readFileSync(indicatorIdePath, 'utf8')
const klineChartSource = fs.readFileSync(klineChartPath, 'utf8')
const strategyIdeSource = fs.readFileSync(strategyIdePath, 'utf8')

test('indicator-to-strategy conversion has a parameter parser', () => {
  assert.match(
    indicatorIdeSource,
    /parseIndicatorParamRaw \(code\) \{[\s\S]*?this\.parseIndicatorParamSpecs\(code \|\| ''\)[\s\S]*?params\[spec\.name\] = spec\.defaultValue/
  )
  assert.match(
    indicatorIdeSource,
    /buildIndicatorToStrategyContext \(\)[\s\S]*?this\.parseIndicatorParamRaw\(code \|\| ''\)/
  )
})

test('indicator IDE no longer carries the retired execution-column conversion prompt', () => {
  assert.doesNotMatch(indicatorIdeSource, /buildIndicatorToStrategyPrompt \(\)/)
  assert.doesNotMatch(indicatorIdeSource, /open_long\/open_short/)
})

test('initial left-edge layout events do not trigger history loading', () => {
  assert.match(
    klineChartSource,
    /const isScrollingLeft = lastVisibleFrom !== null && lastVisibleFrom > data\.from[\s\S]*?if \(isScrollingLeft && canLoadAgain\)/
  )
  assert.doesNotMatch(klineChartSource, /isAlreadyAtEdge/)
  assert.doesNotMatch(
    klineChartSource,
    /formattedData\.length < visibleNeed[\s\S]*?loadMoreHistoryDataForScroll/
  )
})

test('indicator conversion route opens before strategy route initialization can replace it', () => {
  assert.match(
    strategyIdeSource,
    /await this\.loadSources\(\)[\s\S]*?if \(this\.isIndicatorConvertRoute\(\)\) \{[\s\S]*?updateRoute: false[\s\S]*?await this\.applyIndicatorConvertRouteOnce\(\)[\s\S]*?return/
  )
  assert.match(
    strategyIdeSource,
    /indicatorId: String\(raw\.indicatorId \|\| raw\.id \|\| ''\)[\s\S]*?market: String\(raw\.market \|\| ''\)[\s\S]*?timeframe: String\(raw\.timeframe \|\| ''\)/
  )
})

test('indicator-to-strategy conversion preserves the source instrument and timeframe', () => {
  const start = strategyIdeSource.indexOf('resolveIndicatorConversionContext (ctx = {})')
  const end = strategyIdeSource.indexOf('async confirmIndicatorToStrategy ()', start)
  const conversionSource = strategyIdeSource.slice(start, end)

  assert.ok(start >= 0 && end > start)
  assert.match(conversionSource, /resolveIndicatorStrategyContext\(ctx, query, this\.runConfig \|\| \{\}\)/)
  assert.match(conversionSource, /Source instrument: \$\{source\.instrument\}/)
  assert.match(conversionSource, /Source timeframe: \$\{source\.timeframe\}/)
  assert.match(conversionSource, /Never replace them with USStock:SPY/)
  assert.match(conversionSource, /There is no get_current_data API/)
  assert.match(conversionSource, /it has no quantity or cost_basis/)
  assert.match(conversionSource, /never inside initialize\(context\)/)
})

test('indicator conversion resolves Crypto source context without falling back to SPY', () => {
  assert.deepEqual(
    resolveIndicatorStrategyContext({
      market: 'Crypto',
      symbol: 'SOL/USDT',
      exchange_id: 'binance',
      market_type: 'spot',
      timeframe: '1H'
    }),
    {
      market: 'Crypto',
      symbol: 'SOL/USDT',
      exchangeId: 'binance',
      marketType: 'spot',
      timeframe: '1H',
      instrument: 'Crypto:SOL/USDT@binance:spot'
    }
  )
})

test('indicator conversion uses the current strategy context when indicator metadata is generic', () => {
  const resolved = resolveIndicatorStrategyContext({}, {}, {
    market_category: 'Crypto',
    symbol: 'ETH/USDT',
    exchange_id: 'okx',
    market_type: 'swap',
    timeframe: '4H'
  })

  assert.equal(resolved.instrument, 'Crypto:ETH/USDT@okx:swap')
  assert.equal(resolved.timeframe, '4H')
})

test('converted strategy metadata follows the resolved source market context', () => {
  assert.match(
    strategyIdeSource,
    /buildGeneratedMetadata \(ctx = \{\}\)[\s\S]*?const source = this\.resolveIndicatorConversionContext\(ctx\)[\s\S]*?source_indicator_instrument: source\.instrument[\s\S]*?last_run_config: lastRunConfig/
  )
})
