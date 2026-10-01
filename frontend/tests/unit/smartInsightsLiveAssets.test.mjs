import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

import { LIVE_ASSET_ORDER, normalizeLiveAssetRows, formatLiveAssetPrice } from '../../src/views/smart-insights/liveAssets.js'
import { formatVietnamDateTime, formatVietnamTime } from '../../src/utils/vietnamTime.js'

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

test('preserves daily classification and observation time for a HOSE index', () => {
  const rows = normalizeLiveAssetRows({
    assets: [{ displaySymbol: 'VNINDEX', market: 'VNStock', price: 1758.05,
      timeframe: '1D', observedAt: '2026-10-01T00:00:00+00:00', status: 'DAILY' }]
  })
  const index = rows.find(row => row.displaySymbol === 'VNINDEX')
  assert.equal(index.status, 'DAILY')
  assert.equal(index.timeframe, '1D')
  assert.equal(index.observedAt, '2026-10-01T00:00:00+00:00')
})

test('ticker shows the source and Vietnam observation time for daily HOSE data', () => {
  const source = fs.readFileSync(new URL('../../src/views/smart-insights/components/LiveDataSources.vue', import.meta.url), 'utf8')
  const script = source.split('<script>')[1].split('</script>')[0]
    .replace(/^import[^\n]+\n/gm, '').replace('export default', 'globalThis.component =')
  const context = { formatLiveAssetPrice, formatVietnamDateTime, formatVietnamTime }
  vm.runInNewContext(script, context)
  const instance = { $t: key => key, $i18n: { locale: 'vi-VN' } }

  assert.equal(context.component.methods.sourceDetail.call(instance, {
    source: 'vndirect', observedAt: '2026-10-01T00:00:00+00:00'
  }), `vndirect · ${formatVietnamDateTime('2026-10-01T00:00:00+00:00', { locale: 'vi-VN' })}`)
})

test('mounts and cleans the live asset refresh interval', () => {
  const source = fs.readFileSync(new URL('../../src/layouts/BasicLayout.vue', import.meta.url), 'utf8')
  assert.match(source, /LIVE_ASSET_REFRESH_MS\s*=\s*30000/u)
  assert.match(source, /window\.setInterval/u)
  assert.match(source, /window\.clearInterval/u)
  assert.ok(source.indexOf('<live-data-sources') < source.indexOf('<route-view'))
})
