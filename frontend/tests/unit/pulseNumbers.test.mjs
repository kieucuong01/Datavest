import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { finiteValue } from '../../src/views/smart-insights/pulseNumbers.js'

test('unavailable metrics never coerce to zero but real zero stays valid', () => {
  for (const value of [null, undefined, '', ' ', false, NaN, Infinity]) assert.equal(finiteValue(value), null)
  assert.equal(finiteValue(0), 0)
  assert.equal(finiteValue('0'), 0)
  assert.equal(finiteValue(-10), -10)
})

function component (name) {
  const source = readFileSync(new URL(`../../src/views/smart-insights/components/${name}.vue`, import.meta.url), 'utf8')
  const script = source.split('<script>')[1].split('</script>')[0]
    .replace(/import[^\n]+\n/g, '').replace('export default', 'globalThis.component =')
  const context = { finiteValue, DataFreshnessNotice: {}, PulseTrendChart: {} }
  vm.runInNewContext(script, context)
  return context.component
}

test('whale metrics render missing values as unavailable', () => {
  const { methods } = component('WhaleFlowMonitor')
  assert.equal(methods.formatBtc(null), '—')
  assert.equal(methods.formatPercent.call({ locale: 'vi-VN' }, null), '—')
  assert.notEqual(methods.formatBtc(0), '—')
})

test('derivative KPI filters and charts never fabricate zero from null', () => {
  const { filters, computed } = component('DerivativesTerminal')
  for (const filter of Object.values(filters)) {
    assert.equal(filter(null), '—')
    assert.notEqual(filter(0), '—')
  }
  const points = computed.points.call({ derivatives: { series: [{ value: null, effectiveAt: '2026-10-05', symbol: 'BTC' }] } })
  assert.equal(points.length, 0)
})

test('trend and cycle charts omit missing observations', () => {
  const series = [{ value: null, effectiveAt: '2026-10-05', metric: 'index' }]
  assert.equal(component('PulseTrendChart').computed.points.call({ series }).length, 0)
  assert.equal(component('CycleTerminal').computed.rawPoints.call({ cycle: { series } }).length, 0)
})

test('fear/greed comparison requires the requested calendar day', () => {
  const { methods } = component('FearGreedPanel')
  const latest = { effectiveAt: '2026-10-04T00:00:00Z', value: 66 }
  const earlier = { effectiveAt: '2026-09-20T00:00:00Z', value: 20 }
  const context = { latest, points: [earlier, latest] }
  assert.equal(methods.pointDaysAgo.call(context, 1), null)
  assert.equal(methods.pointDaysAgo.call(context, 7), null)
  assert.equal(methods.pointDaysAgo.call(context, 0).value, 66)
})
