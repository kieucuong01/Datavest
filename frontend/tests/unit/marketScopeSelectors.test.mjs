import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

import { canonicalizeSupportedSymbol, normalizeSupportedMarket } from '../../src/utils/supportedMarkets.js'

test('fallback market options contain only supported markets in product order', () => {
  const source = fs.readFileSync(new URL('../../src/utils/marketModules.js', import.meta.url), 'utf8')
  assert.match(source, /FALLBACK_MARKET_MODULES\s*=\s*\[\s*\{ key: 'VNStock'/)
  assert.doesNotMatch(source, /\{ key: 'USStock'/)
  assert.match(source, /\{ key: 'Crypto'/)
  assert.match(source, /\{ key: 'Forex'/)
  assert.doesNotMatch(source, /CNStock|HKStock|Futures|MOEX/)
})

test('frontend cannot canonicalize generic FX or retired markets', () => {
  assert.throws(() => normalizeSupportedMarket('MOEX'))
  assert.throws(() => canonicalizeSupportedSymbol('Forex', 'EURUSD'))
})

test('Smart Insights no longer owns a separate market-filter engine', () => {
  const source = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /markets:\s*\[/)
  assert.doesNotMatch(source, /pulseMarkets:\s*\[/)
  assert.doesNotMatch(source, /markets:\s*\[[^\]]*['"]us['"]/)
  assert.doesNotMatch(source, /markets:\s*\[[^\]]*(?:CNStock|HKStock|Futures|MOEX|macro)/)
})
