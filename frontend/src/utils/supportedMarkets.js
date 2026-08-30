export const SUPPORTED_MARKET_ORDER = ['USStock', 'VNStock', 'Crypto', 'Forex']
export const SUPPORTED_MARKETS = Object.freeze(new Set(SUPPORTED_MARKET_ORDER))
// US stocks remain part of the internal contract so the product can be
// re-enabled later without changing persisted symbols. They are intentionally
// hidden from the current DataVest product surface.
export const ACTIVE_MARKET_ORDER = ['VNStock', 'Crypto', 'Forex']
export const ACTIVE_MARKETS = Object.freeze(new Set(ACTIVE_MARKET_ORDER))

export class UnsupportedSupportedMarketError extends Error {
  constructor (message) {
    super(message)
    this.name = 'UnsupportedSupportedMarketError'
  }
}

const MARKET_ALIASES = Object.freeze({
  us: 'USStock',
  usstock: 'USStock',
  usstocks: 'USStock',
  stock: 'USStock',
  stocks: 'USStock',
  equity: 'USStock',
  equities: 'USStock',
  vn: 'VNStock',
  vietnam: 'VNStock',
  vnstock: 'VNStock',
  vietnamstock: 'VNStock',
  crypto: 'Crypto',
  cryptocurrency: 'Crypto',
  forex: 'Forex',
  fx: 'Forex',
  gold: 'Forex',
  xau: 'Forex'
})

const GOLD_SYMBOL_ALIASES = new Set(['XAU', 'XAUUSD', 'GOLD'])

function marketKey (value) {
  return String(value || '').trim().toLowerCase().replace(/[ _-]/g, '')
}

export function normalizeSupportedMarket (value) {
  const raw = String(value || '').trim()
  const market = MARKET_ALIASES[marketKey(raw)] || raw
  if (!SUPPORTED_MARKETS.has(market)) {
    throw new UnsupportedSupportedMarketError(`Unsupported market '${raw}'`)
  }
  return market
}

export function canonicalizeSupportedSymbol (market, symbol) {
  const canonicalMarket = normalizeSupportedMarket(market)
  const rawSymbol = String(symbol || '').trim().toUpperCase()
  const compactSymbol = rawSymbol.replace(/[ /-]/g, '')
  if (canonicalMarket === 'Forex') {
    if (!GOLD_SYMBOL_ALIASES.has(compactSymbol)) {
      throw new UnsupportedSupportedMarketError('Only Gold/XAU is supported in the Forex provider namespace')
    }
    return 'XAUUSD'
  }
  if (!rawSymbol) throw new Error('Empty symbol')
  return rawSymbol
}

export function isSupportedMarket (value) {
  try {
    normalizeSupportedMarket(value)
    return true
  } catch (error) {
    return false
  }
}

export function isActiveMarket (value) {
  try {
    return ACTIVE_MARKETS.has(normalizeSupportedMarket(value))
  } catch (error) {
    return false
  }
}
