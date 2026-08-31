const MARKET_META = {
  Crypto: { key: 'crypto', color: '#2457c5' },
  VNStock: { key: 'vn_stock', color: '#22ba73' },
  Forex: { key: 'gold', color: '#d59a28' }
}

const safeNumber = (value) => {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

const toPercent = (value, total) => total > 0 ? Number((value / total * 100).toFixed(2)) : 0

export const marketMetaFor = (market) => MARKET_META[market] || { key: String(market || 'other').toLowerCase(), color: '#64748b' }

export function buildPortfolioAnalytics (positions = []) {
  const bySymbolMap = new Map()
  const byCategoryMap = new Map()

  positions.forEach((position) => {
    const marketValue = Math.max(0, safeNumber(position.market_value || safeNumber(position.current_price) * safeNumber(position.quantity)))
    const symbol = String(position.symbol || '—').toUpperCase()
    const meta = marketMetaFor(position.market)
    const symbolKey = `${position.market || 'Other'}:${symbol}`

    const symbolItem = bySymbolMap.get(symbolKey) || {
      symbol,
      market: position.market || 'Other',
      marketValue: 0,
      allocation: 0,
      color: meta.color
    }
    symbolItem.marketValue += marketValue
    bySymbolMap.set(symbolKey, symbolItem)

    const categoryItem = byCategoryMap.get(meta.key) || {
      key: meta.key,
      market: position.market || 'Other',
      marketValue: 0,
      allocation: 0,
      color: meta.color
    }
    categoryItem.marketValue += marketValue
    byCategoryMap.set(meta.key, categoryItem)
  })

  const totalMarketValue = Array.from(bySymbolMap.values()).reduce((total, item) => total + item.marketValue, 0)
  const bySymbol = Array.from(bySymbolMap.values())
    .map((item) => ({ ...item, marketValue: Number(item.marketValue.toFixed(2)), allocation: toPercent(item.marketValue, totalMarketValue) }))
    .sort((left, right) => right.marketValue - left.marketValue)
  const byCategory = Array.from(byCategoryMap.values())
    .map((item) => ({ ...item, marketValue: Number(item.marketValue.toFixed(2)), allocation: toPercent(item.marketValue, totalMarketValue) }))
    .sort((left, right) => right.marketValue - left.marketValue)
  const concentration = totalMarketValue > 0
    ? Number(bySymbol.reduce((total, item) => total + (item.marketValue / totalMarketValue) ** 2, 0).toFixed(4))
    : null

  return {
    totalMarketValue: Number(totalMarketValue.toFixed(2)),
    bySymbol,
    byCategory,
    concentration,
    // These APIs only expose current manual positions. Do not synthesize performance or trades.
    performance: { available: false, points: [] },
    transactions: []
  }
}
