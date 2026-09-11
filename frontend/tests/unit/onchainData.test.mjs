import test from 'node:test'
import assert from 'node:assert/strict'
import { latestMetric, chartEntries } from '../../src/views/smart-insights/onchainData.js'

test('BTC cards never accidentally use ETH; null never becomes zero', () => {
  const rows = [{ metric: 'mvrv', symbol: 'ETH', value: 9, effectiveAt: '2026-09-11' },
    { metric: 'mvrv', symbol: 'BTC', value: 2, effectiveAt: '2026-09-10' },
    { metric: 'mvrv', symbol: 'BTC', value: null, effectiveAt: '2026-09-11' }]
  assert.equal(latestMetric(rows, 'mvrv', 'BTC').value, 2)
})
test('HODL dimensions and providers stay in separate, dated series', () => {
  const series = ['a', 'b'].flatMap(dimension => [2, 1].map(day => ({
    metric: 'crypto.onchain.hodl_waves', dimension, value: day, symbol: 'BTC', source: 'bitview-onchain', effectiveAt: `2026-09-0${day}`
  })))
  const entries = chartEntries(series, 'BTC')
  assert.equal(entries.length, 2)
  assert.deepEqual(entries[0].points.map(p => p.value), [1, 2])
  assert.notEqual(entries[0].key, entries[1].key)
})
