import assert from 'node:assert/strict'
import test from 'node:test'

import { GUEST_ASSETS, applyIndicatorToggle } from '../../src/views/indicator-guest/guestIndicatorState.js'

test('guest chart exposes only the approved shared market assets', () => {
  assert.deepEqual(GUEST_ASSETS.map(asset => asset.displaySymbol), ['BTC', 'VNINDEX', 'XAU'])
  assert.equal(GUEST_ASSETS[0].symbol, 'BTC/USDT')
  assert.equal(GUEST_ASSETS[1].market, 'VNStock')
  assert.equal(GUEST_ASSETS[2].symbol, 'XAUUSD')
})

test('indicator toolbar can add, update, and remove local chart indicators', () => {
  const added = applyIndicatorToggle([], { action: 'add', indicator: { id: 'ema', instanceId: 'ema-1', params: { length: 20 } } })
  assert.equal(added.length, 1)
  const updated = applyIndicatorToggle(added, { action: 'update', indicator: { id: 'ema', instanceId: 'ema-1', params: { length: 50 } } })
  assert.equal(updated[0].params.length, 50)
  assert.deepEqual(applyIndicatorToggle(updated, { action: 'remove', indicator: { id: 'ema', instanceId: 'ema-1' } }), [])
})
