import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const pageSource = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
const pulseSource = fs.readFileSync(new URL('../../src/views/smart-insights/components/MarketPulseSection.vue', import.meta.url), 'utf8')
const layoutSource = fs.readFileSync(new URL('../../src/layouts/BasicLayout.vue', import.meta.url), 'utf8')

test('Smart Insights caches stable datasets and keys date-scoped data by asOf', () => {
  assert.match(pageSource, /smartInsightsCache/u)
  assert.match(pageSource, /cacheKey.*asOf|asOf.*cacheKey/u)
  assert.match(pageSource, /loadOverview\(requestId, force\)/u)
  assert.match(pageSource, /loadPulse\(requestId, force\)/u)
  assert.doesNotMatch(pageSource, /loadWatchlist\(requestId, force\)/u)
  assert.match(pageSource, /response\.data\.assets/u)
  assert.match(pageSource, /loadDates\(requestId, force\)/u)
  assert.match(pageSource, /loadCalendar\(force, requestId\)/u)
  assert.doesNotMatch(pageSource, /class="analysis-controls"/u)
  assert.doesNotMatch(pageSource, /@change="handleDateChange"/u)
  assert.match(pageSource, /retrySection\s*\(section\)/u)
  assert.doesNotMatch(pageSource, /retryAll|await this\.loadAll\(true\)/u)
})

test('Smart Insights prefetches crypto terminals during the initial page load', () => {
  assert.match(pageSource, /loadPulseDetails\(requestId, force\)/u)
  assert.doesNotMatch(pageSource, /cryptoTerminalsReady|requestIdleCallback|scheduleCryptoTerminals|near-viewport/u)
  assert.doesNotMatch(pulseSource, /IntersectionObserver|cryptoReady|near-viewport/u)
  assert.match(pulseSource, /activeKey === 'crypto' && !coreReady/u)
  assert.match(pulseSource, /onchainLoading/u)
})

test('Global live ticker polls continuously only while Smart Insights is active', () => {
  assert.match(layoutSource, /syncLiveAssetPolling/u)
  assert.match(layoutSource, /\$route\.path/u)
  assert.match(layoutSource, /LIVE_ASSET_REFRESH_MS/u)
  assert.match(layoutSource, /isSmartInsightsRoute|path === '\/smart-insights'/u)
})
