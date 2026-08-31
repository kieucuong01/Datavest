import test from 'node:test'
import assert from 'node:assert/strict'

import { buildPortfolioAnalytics } from '../../src/views/mock-portfolio/portfolioAnalytics.js'

test('builds allocation analytics from live holdings without inventing performance history', () => {
  const analytics = buildPortfolioAnalytics([
    { symbol: 'BTC', market: 'Crypto', market_value: 9000 },
    { symbol: 'HPG', market: 'VNStock', market_value: 2000 },
    { symbol: 'XAU', market: 'Forex', market_value: 1000 }
  ])

  assert.equal(analytics.totalMarketValue, 12000)
  assert.deepEqual(
    analytics.bySymbol.map((item) => [item.symbol, item.marketValue, item.allocation]),
    [
      ['BTC', 9000, 75],
      ['HPG', 2000, 16.67],
      ['XAU', 1000, 8.33]
    ]
  )
  assert.equal(analytics.byCategory.find((item) => item.key === 'crypto').allocation, 75)
  assert.equal(analytics.performance.available, false)
  assert.deepEqual(analytics.performance.points, [])
  assert.deepEqual(analytics.transactions, [])
})
