import assert from 'node:assert/strict'
import test from 'node:test'
import { hosePilotRows, hoseResearchNumber } from '../../src/utils/hoseResearch.js'

test('pilot follows exact VNStock membership and excludes benchmark indices', () => {
  const assets = ['FPT', 'HPG', 'VCB', 'VNINDEX'].map(symbol => ({ market: 'VNStock', symbol }))
  const rows = hosePilotRows(assets, [{ market: 'VNStock', symbol: 'FPT' }, { market: 'Crypto', symbol: 'HPG' }])
  assert.deepEqual(rows.map(row => [row.symbol, row.following]), [['FPT', true], ['HPG', false], ['VCB', false]])
})

test('missing research metrics stay unavailable while a real zero is visible', () => {
  assert.equal(hoseResearchNumber(null, 'VND'), '—')
  assert.equal(hoseResearchNumber(undefined), '—')
  assert.equal(hoseResearchNumber(0, 'VND'), '0 VND')
})
