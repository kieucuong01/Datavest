import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const page = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
const liveSources = fs.readFileSync(new URL('../../src/views/smart-insights/components/LiveDataSources.vue', import.meta.url), 'utf8')
const marketPulse = fs.readFileSync(new URL('../../src/views/smart-insights/components/MarketPulseSection.vue', import.meta.url), 'utf8')

test('Smart Insights MVP is watchlist-first and keeps the daily brief surface', () => {
  assert.match(page, /getWatchlist/u)
  assert.match(page, /buildWatchlistOpinionRows/u)
  assert.match(page, /daily-hero/u)
  assert.match(page, /cryptoPulse/u)
})

test('Smart Insights MVP renders live source status and keeps detail terminals', () => {
  assert.match(liveSources, /statusLabel/u)
  assert.match(liveSources, /fetchedAtLabel/u)
  assert.match(marketPulse, /FearGreedPanel|FlowTerminal|DerivativesTerminal|CycleTerminal|OnchainTerminal/u)
  assert.doesNotMatch(marketPulse, /pulse-chart-grid|PulseTrendChart/u)
  assert.match(marketPulse, /statusLabel/u)
})
