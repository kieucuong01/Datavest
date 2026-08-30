import assert from 'node:assert/strict'
import test from 'node:test'

import { buildWatchlistOpinionRows } from '../../src/views/smart-insights/watchlistOpinions.js'

test('renders only watchlist assets in watchlist order', () => {
  const rows = buildWatchlistOpinionRows(
    [
      { market: 'Crypto', symbol: 'ETH/USDT', name: 'Ethereum' },
      { market: 'VNStock', symbol: 'FPT', name: 'FPT' }
    ],
    [
      { market: 'crypto', symbol: 'BTC', stance: 'POSITIVE' },
      { market: 'crypto', symbol: 'ETH', stance: 'NEUTRAL' },
      { market: 'vn', symbol: 'FPT', stance: 'POSITIVE' }
    ]
  )
  assert.deepEqual(rows.map(row => row.symbol), ['ETH/USDT', 'FPT'])
  assert.equal(rows[0].opinion.stance, 'NEUTRAL')
  assert.equal(rows[1].opinion.stance, 'POSITIVE')
})

test('keeps a watchlist row when analysis is unavailable', () => {
  const [row] = buildWatchlistOpinionRows(
    [{ market: 'Forex', symbol: 'XAUUSD', name: 'Gold' }],
    []
  )
  assert.equal(row.analysisStatus, 'UNAVAILABLE')
  assert.equal(row.opinion, null)
})
