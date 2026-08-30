export const LIVE_ASSET_ORDER = ['BTC', 'ETH', 'SOL', 'XRP', 'LINK', 'VNINDEX', 'VN30', 'XAU']

function finitePositive (value) {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? number : null
}

export function normalizeLiveAssetRows (payload = {}) {
  const indexed = new Map(
    (Array.isArray(payload.assets) ? payload.assets : [])
      .filter(item => item && item.displaySymbol)
      .map(item => [String(item.displaySymbol).toUpperCase(), item])
  )
  return LIVE_ASSET_ORDER.map(displaySymbol => {
    const item = indexed.get(displaySymbol) || {}
    const price = finitePositive(item.price)
    return {
      displaySymbol,
      market: item.market || '',
      symbol: item.symbol || '',
      price,
      change: Number.isFinite(Number(item.change)) ? Number(item.change) : 0,
      changePercent: Number.isFinite(Number(item.changePercent)) ? Number(item.changePercent) : 0,
      source: item.source || '',
      sourceExchangeId: item.sourceExchangeId || '',
      sourceMarketType: item.sourceMarketType || '',
      cached: Boolean(item.cached),
      stale: Boolean(item.stale),
      status: item.status === 'STALE' || item.status === 'LIVE' ? item.status : price ? 'LIVE' : 'UNAVAILABLE'
    }
  })
}

export function formatLiveAssetPrice (value, displaySymbol = '') {
  const number = finitePositive(value)
  if (number === null) return '—'
  const maximumFractionDigits = displaySymbol === 'VNINDEX' || displaySymbol === 'VN30' ? 2 : number >= 1000 ? 0 : 4
  return new Intl.NumberFormat('en-US', { maximumFractionDigits }).format(number)
}
