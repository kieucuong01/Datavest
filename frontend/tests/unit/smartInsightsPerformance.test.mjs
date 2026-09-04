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
  assert.match(pageSource, /loadWatchlist\(requestId, force\)/u)
  assert.match(pageSource, /loadDates\(requestId, force\)/u)
  assert.match(pageSource, /loadCalendar\(force, requestId\)/u)
  assert.match(pageSource, /@change="handleDateChange"/u)
  assert.match(pageSource, /handleDateChange\s*\(\) \{ return this\.loadAll\(false\)/u)
  assert.match(pageSource, /await this\.loadAll\(true\)/u)
})

test('Smart Insights defers crypto terminals until the first page render is ready', () => {
  assert.match(pageSource, /cryptoTerminalsReady/u)
  assert.match(pageSource, /requestIdleCallback|scheduleCryptoTerminals/u)
  assert.match(pageSource, /crypto-ready/u)
  assert.match(pulseSource, /cryptoReady/u)
  assert.match(pulseSource, /activeKey === 'crypto' && !cryptoReady/u)
})

test('Global live ticker polls continuously only while Smart Insights is active', () => {
  assert.match(layoutSource, /syncLiveAssetPolling/u)
  assert.match(layoutSource, /\$route\.path/u)
  assert.match(layoutSource, /LIVE_ASSET_REFRESH_MS/u)
  assert.match(layoutSource, /isSmartInsightsRoute|path === '\/smart-insights'/u)
})
