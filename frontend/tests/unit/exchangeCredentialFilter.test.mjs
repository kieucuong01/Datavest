import assert from 'node:assert/strict'
import test from 'node:test'

import { filterCryptoExchangeCredentials } from '../../src/utils/exchangeCredential.js'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dirname = path.dirname(fileURLToPath(import.meta.url))

test('keeps every account for the selected crypto exchange', () => {
  const credentials = [
    { id: 1, exchange_id: 'binance', name: 'Binance 1' },
    { id: 2, exchange_id: ' BINANCE ', name: 'Binance 2' },
    { id: 3, exchange_id: 'Binance', name: 'Binance 3' },
    { id: 4, exchange_id: 'okx', name: 'OKX 1' },
    { id: 5, exchange_id: 'unsupported', name: 'Unsupported' }
  ]

  assert.deepEqual(
    filterCryptoExchangeCredentials(credentials, 'binance').map(item => item.id),
    [1, 2, 3]
  )
  assert.deepEqual(
    filterCryptoExchangeCredentials(credentials, 'okx').map(item => item.id),
    [4]
  )
})

test('returns all supported crypto accounts when no exchange is selected', () => {
  const credentials = [
    { id: 1, exchange_id: 'binance' },
    { id: 2, exchange_id: 'okx' },
    { id: 3, exchange_id: 'alpaca' }
  ]

  assert.deepEqual(
    filterCryptoExchangeCredentials(credentials, '').map(item => item.id),
    [1, 2]
  )
})

test('retired crypto broker account card stays absent', () => {
  const component = path.resolve(dirname, '../../src/views/broker-accounts/components/CryptoExchangeAccountsCard.vue')

  assert.equal(existsSync(component), false)
})
