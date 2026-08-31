import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

import { MARKET_PULSE_TABS, buildPulsePanel, normalizePulseSeries } from '../../src/views/smart-insights/marketPulse.js'

test('merges BTC whale flow into the evidence-backed flows tab and keeps no forecast surface', () => {
  assert.deepEqual(MARKET_PULSE_TABS.map(tab => tab.key), [
    'overview', 'flows', 'sentiment', 'derivatives', 'cycle', 'onchain'
  ])
  assert.equal(JSON.stringify(MARKET_PULSE_TABS).match(/forecast|kronos|btcbottom/iu), null)
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

test('market pulse component consumes every supported tab without forecast copy', () => {
  const source = fs.readFileSync(new URL('../../src/views/smart-insights/components/MarketPulseSection.vue', import.meta.url), 'utf8')
  const modelSource = fs.readFileSync(new URL('../../src/views/smart-insights/marketPulse.js', import.meta.url), 'utf8')
  for (const key of ['overview', 'flows', 'sentiment', 'derivatives', 'cycle', 'onchain']) {
    assert.match(modelSource, new RegExp(`['"]${key}['"]`, 'u'))
  }
  assert.match(source, /MARKET_PULSE_TABS|activeKey|tabs/u)
  assert.match(source, /PulseTrendChart/u)
  assert.equal(source.match(/forecast|kronos|btcBottom/iu), null)
})
