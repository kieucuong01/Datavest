import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { runSectionLoaders } from '../../src/views/smart-insights/loadingCoordinator.js'
import { isCurrentRequest, summarizeReadiness, vietnamToday } from '../../src/views/smart-insights/dataReadiness.js'
import { normalizePulseSeries } from '../../src/views/smart-insights/marketPulse.js'
import { calendarCacheFresh } from '../../src/views/smart-insights/calendarRefresh.js'

function page (api = {}) {
  const source = readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
  const script = source.split('<script>')[1].split('</script>')[0]
    .replace(/import[^\n]+\n/g, '').replace('export default', 'globalThis.component =')
  const context = {
    mapState: () => ({}), AssetOpinionsSection: {}, EconomicCalendarTable: {}, MarketPulseSection: {}, DeepAnalysisPanel: {}, ReportPdfReader: {},
    runSectionLoaders, isCurrentRequestToken: isCurrentRequest, summarizeReadiness, vietnamToday, calendarCacheFresh,
    getSmartInsightsOverview: async () => ({ data: { status: 'AVAILABLE' } }),
    getSmartInsightsCryptoPulse: async () => ({ data: { status: 'AVAILABLE' } }),
    getEconomicCalendar: async () => ({ code: 1, data: [], meta: {} }),
    getWatchlist: async () => ({ data: [] }), getSmartInsightsDataHealth: async () => ({ data: { sources: [] } }),
    ...api
  }
  vm.runInNewContext(script, context)
  const definition = context.component
  const instance = { ...definition.data(), $t: key => key, $i18n: { locale: 'vi-VN' } }
  Object.entries(definition.methods).forEach(([key, fn]) => { instance[key] = fn.bind(instance) })
  instance.asOf = '2026-09-07'
  instance.smartInsightsCache.dates = ['2026-09-07', '2026-09-06']
  return { instance, definition }
}

function marketPulseSection (browser = {}) {
  const source = readFileSync(new URL('../../src/views/smart-insights/components/MarketPulseSection.vue', import.meta.url), 'utf8')
  const script = source.split('<script>')[1].split('</script>')[0]
    .replace(/^import[^\n]+\n/gm, '').replace('export default', 'globalThis.component =')
  const context = {
    window: browser,
    MARKET_PULSE_TABS: [],
    buildPulsePanel: () => ({}),
    pulseTabLabel: tab => tab && tab.key
  }
  vm.runInNewContext(script, context)
  const definition = context.component
  const emitted = []
  const instance = {
    ...definition.data(),
    $el: {},
    $emit: event => emitted.push(event)
  }
  Object.entries(definition.methods).forEach(([key, fn]) => { instance[key] = fn.bind(instance) })
  return { definition, emitted, instance }
}
const deferred = () => {
  let resolve, reject
  const promise = new Promise((a, b) => { resolve = a; reject = b })
  return { promise, resolve, reject }
}
const tick = () => new Promise(resolve => setImmediate(resolve))

test('selected date starts overview without waiting for the dates endpoint', async () => {
  const dates = deferred()
  let overviewCalls = 0
  const { instance: p } = page({
    getSmartInsightsDates: () => dates.promise,
    getSmartInsightsOverview: async () => { overviewCalls++; return { data: { status: 'AVAILABLE' } } }
  })
  p.smartInsightsCache.dates = null
  const loading = p.loadAll()
  await tick()
  const callsBeforeDates = overviewCalls
  dates.resolve({ data: { dates: ['2026-09-07'] } })
  await loading
  assert.equal(callsBeforeDates, 1)
})

test('pulse completion does not eagerly schedule heavy terminals', async () => {
  const calendar = deferred()
  const { instance: p } = page({ getEconomicCalendar: () => calendar.promise })
  let scheduled = 0
  p.scheduleCryptoTerminals = () => { scheduled++ }
  const loading = p.loadAll()
  await tick()
  assert.equal(scheduled, 0)
  calendar.resolve({ code: 1, data: [] })
  await loading
  assert.equal(scheduled, 0)
})

test('first visit starts latest overview and pulse without waiting for dates', async () => {
  const dates = deferred()
  const overviewDates = []
  const pulseDates = []
  const { instance: p } = page({
    getSmartInsightsDates: () => dates.promise,
    getSmartInsightsOverview: async args => {
      overviewDates.push(args.as_of)
      return { data: { assets: [{ market: 'Crypto', symbol: 'BTC/USDT', displaySymbol: 'BTC' }] } }
    },
    getSmartInsightsCryptoPulse: async args => {
      pulseDates.push(args.as_of)
      return { data: { status: 'AVAILABLE' } }
    }
  })
  p.asOf = undefined
  p.smartInsightsCache.dates = null
  const loading = p.loadAll()
  await tick()
  assert.deepEqual(overviewDates, [undefined])
  assert.deepEqual(pulseDates, [undefined])
  dates.resolve({ data: { dates: ['2026-09-08', '2026-09-07'] } })
  await loading
  assert.equal(p.asOf, '2026-09-08')
  assert.deepEqual(p.watchlist.map(asset => asset.displaySymbol), ['BTC'])
})

test('market pulse requests heavy terminals only when it nears the viewport', () => {
  let observer
  class FakeIntersectionObserver {
    constructor (callback, options) {
      this.callback = callback
      this.options = options
      this.disconnected = false
      observer = this
    }

    observe (element) { this.element = element }
    disconnect () { this.disconnected = true }
  }

  const { definition, emitted, instance } = marketPulseSection({ IntersectionObserver: FakeIntersectionObserver })
  definition.mounted.call(instance)

  assert.equal(observer.element, instance.$el)
  assert.equal(observer.options.rootMargin, '160px 0px')
  observer.callback([{ isIntersecting: false }])
  assert.deepEqual(emitted, [])
  observer.callback([{ isIntersecting: true }])
  assert.deepEqual(emitted, ['near-viewport'])
  assert.equal(observer.disconnected, true)
})

test('market pulse loads terminals immediately when viewport observation is unavailable', () => {
  const { definition, emitted, instance } = marketPulseSection({})
  definition.mounted.call(instance)
  assert.deepEqual(emitted, ['near-viewport'])
})

test('retry pulse touches only pulse and does not invalidate concurrent overview', async () => {
  const pending = deferred()
  let pulseCalls = 0, overviewCalls = 0, calendarCalls = 0
  const { instance: p } = page({
    getSmartInsightsOverview: () => { overviewCalls++; return pending.promise },
    getSmartInsightsCryptoPulse: async () => { pulseCalls++; return { data: { status: 'AVAILABLE' } } },
    getEconomicCalendar: async () => { calendarCalls++; return { code: 1, data: [] } }
  })
  const loading = p.loadAll()
  await tick()
  await p.retrySection('pulse')
  assert.equal(overviewCalls, 1)
  assert.equal(calendarCalls, 1)
  assert.equal(pulseCalls, 2)
  assert.equal(p.overviewLoading, true)
  pending.resolve({ data: { marker: 'overview' } })
  await loading
  assert.equal(p.overview.marker, 'overview')
  assert.equal(p.overviewLoading, false)
})

test('older same-section retry cannot overwrite refreshed result or cache', async () => {
  const old = deferred(), recent = deferred()
  let calls = 0
  const { instance: p } = page({ getSmartInsightsCryptoPulse: () => ++calls === 1 ? old.promise : recent.promise })
  const first = p.retrySection('pulse'), second = p.retrySection('pulse')
  recent.resolve({ data: { marker: 'new' } })
  await second
  old.resolve({ data: { marker: 'old' } })
  await first
  assert.equal(p.cryptoPulse.marker, 'new')
  assert.equal(p.smartInsightsCache.pulse.get(p.cacheKey()).marker, 'new')
  assert.equal(p.pulseLoading, false)
})

test('changing date clears old reports even when the next date fails; calendar is date scoped', async () => {
  const calendarDates = []
  let failed = false
  const { instance: p } = page({
    getSmartInsightsOverview: async () => { if (failed) throw new Error('502 HTML'); return { data: { marker: 'old' } } },
    getEconomicCalendar: async args => { calendarDates.push(args.as_of); return { code: 1, data: [] } }
  })
  await p.loadAll()
  failed = true
  p.asOf = '2026-09-06'
  await p.loadAll()
  assert.equal(p.overview, null)
  assert.equal(p.sectionErrors.overview, true)
  assert.deepEqual(calendarDates, ['2026-09-07', '2026-09-06'])
  assert.equal(p.errorMessage.includes('502'), false)
  assert.equal(p.overviewLoading, false)
})

test('older date cannot pollute cache after a newer selection', async () => {
  const old = deferred()
  const { instance: p } = page({ getSmartInsightsOverview: args => args.as_of === '2026-09-07' ? old.promise : Promise.resolve({ data: { marker: 'selected' } }) })
  const first = p.loadAll()
  p.asOf = '2026-09-06'
  await p.loadAll()
  old.resolve({ data: { marker: 'old' } })
  await first
  assert.equal(p.overview.marker, 'selected')
  assert.equal(p.smartInsightsCache.overview.has('2026-09-07|vi-VN'), false)
})

test('evidence switching and closing ignore obsolete responses', async () => {
  const a = deferred(), b = deferred()
  const { instance: p } = page({ getSmartInsightsEvidence: id => id === 'a' ? a.promise : b.promise })
  const first = p.openEvidence('a'), second = p.openEvidence('b')
  a.resolve({ data: { id: 'a' } })
  await first
  assert.equal(p.evidence, null)
  assert.equal(p.evidenceLoading, true)
  p.closeEvidence()
  b.resolve({ data: { id: 'b' } })
  await second
  assert.equal(p.evidence, null)
  assert.equal(p.evidenceVisible, false)
  assert.equal(p.evidenceLoading, false)
})

test('navigation cancels speech and invalidates pending requests', () => {
  let cancelled = 0
  const { instance: p, definition } = page({ window: { speechSynthesis: { cancel: () => cancelled++ }, clearInterval: () => {} } })
  p.heroSpeechActive = true
  const old = p.requestSequence
  definition.beforeDestroy.call(p)
  assert.equal(cancelled, 1)
  assert.equal(p.heroSpeechActive, false)
  assert.equal(p.isCurrentRequest(old), false)
})

test('unknown and failed data states cannot be labelled ready', () => {
  for (const status of ['ERROR', 'FAILED', '', 'UNKNOWN', 'PARTIAL']) {
    assert.notEqual(summarizeReadiness([{ status }]).status, 'READY')
  }
})

test('missing pulse values are not converted into fabricated zero observations', () => {
  const series = [null, undefined, '', '  ', false, 0, '0', 12].map(value => ({ effectiveAt: '2026-09-07', value }))
  assert.deepEqual(normalizePulseSeries(series).map(row => row.value), [0, 0, 12])
})

test('ETF terminal preserves missing values and an empty feed has no zero-valued dashboard', () => {
  const source = readFileSync(new URL('../../src/views/smart-insights/components/FlowTerminal.vue', import.meta.url), 'utf8')
  const script = source.split('<script>')[1].split('</script>')[0]
    .replace(/import[^\n]+\n/g, '').replace('export default', 'globalThis.component =')
  const context = { normalizePulseSeries }
  vm.runInNewContext(script, context)
  const { methods, computed } = context.component
  assert.equal(methods.formatFlow(null), '—')
  assert.equal(methods.formatFlow(undefined), '—')
  assert.notEqual(methods.formatFlow(0), '—')
  assert.equal(methods.sum([]), null)
  assert.equal(computed.rawPoints.call({ flow: { series: [{ effectiveAt: '2026-09-07', symbol: 'BTC', value: null }] } }).length, 0)
  assert.match(source, /v-if="rawPoints.length"/)
})
