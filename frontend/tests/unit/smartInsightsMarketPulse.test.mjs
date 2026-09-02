import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

import { MARKET_PULSE_TABS, buildPulsePanel, normalizePulseSeries } from '../../src/views/smart-insights/marketPulse.js'

test('organizes market pulse into macro, equities, and crypto without a forecast surface', () => {
  assert.deepEqual(MARKET_PULSE_TABS.map(tab => tab.key), [
    'macro', 'equities', 'crypto'
  ])
  assert.equal(JSON.stringify(MARKET_PULSE_TABS).match(/forecast|kronos|btcbottom/iu), null)
})

test('builds one crypto overview from source-backed flow, sentiment, derivatives, cycle, and on-chain data', () => {
  const panel = buildPulsePanel({ tabs: {
    flows: { sources: [{ code: 'etf' }], metrics: [{ metric: 'crypto.etf.net_flow_usd', value: 120 }] },
    sentimentDerivatives: { sources: [{ code: 'fear-greed' }], metrics: [
      { metric: 'crypto.fear_greed.index', value: 60 },
      { metric: 'crypto.derivatives.funding_rate', value: 0.01 }
    ] },
    cycle: { sources: [{ code: 'cbbi' }], metrics: [{ metric: 'crypto.cbbi', value: 48 }] },
    onchain: { sources: [{ code: 'whales' }], metrics: [{ metric: 'crypto.address_balance_btc', value: 1000 }] }
  } }, 'crypto')

  assert.equal(panel.sources.length, 4)
  assert.deepEqual(panel.metrics.map(row => row.metric), [
    'crypto.etf.net_flow_usd',
    'crypto.fear_greed.index',
    'crypto.derivatives.funding_rate',
    'crypto.cbbi',
    'crypto.address_balance_btc'
  ])
})

test('passes the persisted on-chain groups into the crypto terminal adapter', () => {
  const panel = buildPulsePanel({ tabs: {
    onchain: {
      status: 'AVAILABLE',
      sources: [{ source: 'coinmetrics-community' }],
      groups: [{ key: 'valuation', status: 'AVAILABLE', metrics: [{ metric: 'crypto.onchain.mvrv', value: 1.8 }] }],
      series: [{ effectiveAt: '2026-09-01', value: 1.8, metric: 'crypto.onchain.mvrv', symbol: 'BTC' }]
    }
  } }, 'crypto')

  assert.deepEqual(panel.groups.map(group => group.key), ['valuation'])
  assert.equal(panel.groups[0].metrics[0].metric, 'crypto.onchain.mvrv')
  assert.equal(panel.series.some(point => point.metric === 'crypto.onchain.mvrv'), true)
})

test('keeps the backend whale-flow contract with the flows panel', () => {
  const whaleFlows = {
    status: 'AVAILABLE',
    insight: { tone: 'ACCUMULATION', confidence: 'MEDIUM' },
    cohort: { latestChange: { value: 1250 } },
    exchangePressure: { latestNetflow: { value: -800 } }
  }
  const panel = buildPulsePanel({ tabs: { flows: { status: 'AVAILABLE', whaleFlows, etfFlows: { series: [] } } } }, 'flows')
  assert.equal(panel.whaleFlows.insight.tone, 'ACCUMULATION')
  assert.equal(panel.whaleFlows.exchangePressure.latestNetflow.value, -800)
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

test('shows the economic calendar before the three-tab market pulse without forecast copy', () => {
  const source = fs.readFileSync(new URL('../../src/views/smart-insights/components/MarketPulseSection.vue', import.meta.url), 'utf8')
  const modelSource = fs.readFileSync(new URL('../../src/views/smart-insights/marketPulse.js', import.meta.url), 'utf8')
  const pageSource = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
  for (const key of ['macro', 'equities', 'crypto']) {
    assert.match(modelSource, new RegExp(`['"]${key}['"]`, 'u'))
  }
  assert.match(source, /MARKET_PULSE_TABS|activeKey|tabs/u)
  assert.doesNotMatch(source, /PulseTrendChart|pulse-metric-grid--summary|pulse-chart-grid|cryptoPulseTitle/u)
  assert.ok(pageSource.indexOf('<economic-calendar-table') < pageSource.indexOf('<market-pulse-section'))
  assert.equal(source.match(/forecast|kronos|btcBottom/iu), null)
})
