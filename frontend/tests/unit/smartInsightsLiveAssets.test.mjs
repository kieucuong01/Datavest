import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

import { LIVE_ASSET_ORDER, normalizeLiveAssetRows } from '../../src/views/smart-insights/liveAssets.js'

test('normalizes the exact live asset order without inventing missing prices', () => {
  const rows = normalizeLiveAssetRows({
    fetchedAt: '2026-08-29T00:00:00Z',
    assets: [{ displaySymbol: 'BTC', price: 77000, changePercent: 1, status: 'LIVE' }]
  })
  assert.deepEqual(rows.map(row => row.displaySymbol), LIVE_ASSET_ORDER)
  assert.equal(rows[0].price, 77000)
  assert.equal(rows[1].price, null)
  assert.equal(rows[1].status, 'UNAVAILABLE')
})

test('mounts and cleans the live asset refresh interval', () => {
  const source = fs.readFileSync(new URL('../../src/layouts/BasicLayout.vue', import.meta.url), 'utf8')
  assert.match(source, /LIVE_ASSET_REFRESH_MS\s*=\s*30000/u)
  assert.match(source, /window\.setInterval/u)
  assert.match(source, /window\.clearInterval/u)
  assert.ok(source.indexOf('<live-data-sources') < source.indexOf('<route-view'))
})
