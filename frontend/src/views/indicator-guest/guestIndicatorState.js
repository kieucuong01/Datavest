export const GUEST_ASSETS = Object.freeze([
  { market: 'Crypto', symbol: 'BTC/USDT', displaySymbol: 'BTC', name: 'Bitcoin', exchangeId: 'binance', marketType: 'spot' },
  { market: 'VNStock', symbol: 'VNINDEX', displaySymbol: 'VNINDEX', name: 'VN-Index', exchangeId: '', marketType: '' },
  { market: 'Forex', symbol: 'XAUUSD', displaySymbol: 'XAU', name: 'Gold Spot', exchangeId: '', marketType: '' }
])

function indicatorKey (indicator = {}) {
  return indicator.instanceId || indicator.id
}

export function applyIndicatorToggle (current, change = {}) {
  const indicators = Array.isArray(current) ? current : []
  const indicator = change.indicator || {}
  const key = indicatorKey(indicator)
  if (!indicator.id || !key) return indicators.slice()

  if (change.action === 'remove') {
    return indicators.filter(item => indicatorKey(item) !== key && (!indicator.instanceId && item.id !== indicator.id))
  }
  if (change.action === 'update') {
    return indicators.map(item => indicatorKey(item) === key ? { ...item, ...indicator } : item)
  }
  if (change.action === 'add') {
    return [...indicators, { ...indicator }]
  }
  return indicators.slice()
}
