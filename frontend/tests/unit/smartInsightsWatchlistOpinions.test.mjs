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
      { market: 'crypto', symbol: 'BTC', report: { id: 1, decision: 'BUY' } },
      { market: 'crypto', symbol: 'ETH', report: { id: 2, decision: 'HOLD' } },
      { market: 'vn', symbol: 'FPT', report: { id: 3, decision: 'BUY' } }
    ]
  )
  assert.deepEqual(rows.map(row => row.symbol), ['ETH/USDT', 'FPT'])
  assert.equal(rows[0].report.decision, 'HOLD')
  assert.equal(rows[1].report.decision, 'BUY')
})

test('keeps a watchlist row when analysis is unavailable', () => {
  const [row] = buildWatchlistOpinionRows(
    [{ market: 'Forex', symbol: 'XAUUSD', name: 'Gold' }],
    []
  )
  assert.equal(row.analysisStatus, 'UNAVAILABLE')
  assert.equal(row.report, null)
})
