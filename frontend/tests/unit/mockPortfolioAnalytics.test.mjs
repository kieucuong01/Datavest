import test from 'node:test'
import assert from 'node:assert/strict'

import { buildPortfolioAnalytics } from '../../src/views/mock-portfolio/portfolioAnalytics.js'

test('builds allocation analytics from live holdings without inventing performance history', () => {
  const analytics = buildPortfolioAnalytics([
    { symbol: 'BTC', market: 'Crypto', market_value: 9000 },
    { symbol: 'ETH', market: 'Crypto', market_value: 2000 },
    { symbol: 'SOL', market: 'Crypto', market_value: 1000 }
  ])

  assert.equal(analytics.totalMarketValue, 12000)
  assert.deepEqual(
    analytics.bySymbol.map((item) => [item.symbol, item.marketValue, item.allocation]),
    [
      ['BTC', 9000, 75],
      ['ETH', 2000, 16.67],
      ['SOL', 1000, 8.33]
    ]
  )
  assert.equal(analytics.byCategory.find((item) => item.key === 'crypto').allocation, 100)
  assert.equal(analytics.performance.available, false)
  assert.deepEqual(analytics.performance.points, [])
  assert.deepEqual(analytics.transactions, [])
})

test('does not infer cross-currency allocation or missing-price concentration', () => {
  for (const positions of [
    [{ market: 'VNStock', symbol: 'FPT', market_value: 1000000 }, { market: 'Crypto', symbol: 'BTC/USDT', market_value: 80000 }],
    [{ market: 'Crypto', symbol: 'BTC/USDT', market_value: 80000 }, { market: 'Crypto', symbol: 'ETH/USDT', market_value: null, valuation_status: 'UNAVAILABLE' }]
  ]) {
    const analytics = buildPortfolioAnalytics(positions)
    assert.equal(analytics.totalMarketValue, null)
    assert.equal(analytics.concentration, null)
    assert.deepEqual(analytics.byCategory, [])
  }
})
