import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ACTIVE_MARKET_ORDER,
  SUPPORTED_MARKET_ORDER,
  canonicalizeSupportedSymbol,
  isActiveMarket,
  normalizeSupportedMarket
} from '../../src/utils/supportedMarkets.js'

test('exposes only the three active product markets', () => {
  assert.deepEqual(ACTIVE_MARKET_ORDER, ['VNStock', 'Crypto', 'Forex'])
  assert.deepEqual(SUPPORTED_MARKET_ORDER, ['USStock', 'VNStock', 'Crypto', 'Forex'])
  assert.equal(isActiveMarket('USStock'), false)
  assert.equal(isActiveMarket('VNStock'), true)
})

test('canonicalizes gold aliases and rejects other forex pairs', () => {
  assert.equal(canonicalizeSupportedSymbol('Forex', 'XAU/USD'), 'XAUUSD')
  assert.equal(canonicalizeSupportedSymbol('gold', 'XAU-USD'), 'XAUUSD')
  assert.throws(() => canonicalizeSupportedSymbol('Forex', 'EURUSD'))
  assert.throws(() => normalizeSupportedMarket('MOEX'))
})
