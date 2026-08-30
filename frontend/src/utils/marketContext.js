import { canonicalizeSupportedSymbol, normalizeSupportedMarket } from './supportedMarkets.js'

export const CRYPTO_EXCHANGE_IDS = ['binance', 'bitget', 'bybit', 'okx', 'gate', 'htx']

export function normalizeMarketType (value, market = 'Crypto') {
  if (market !== 'Crypto') return 'spot'
  const raw = String(value || '').trim().toLowerCase()
  if (['future', 'futures', 'perp', 'perpetual'].includes(raw)) return 'swap'
  return raw === 'swap' ? 'swap' : 'spot'
}

export function normalizeExchangeId (value) {
  const raw = String(value || '').trim().toLowerCase()
  const aliases = {
    okex: 'okx',
    gateio: 'gate',
    huobi: 'htx',
    binanceusdm: 'binance'
  }
  return aliases[raw] || raw
}

export function marketContextKey (context = {}) {
  const rawSymbol = String(context.symbol || '')
  const symbol = rawSymbol.split(':').find(part => part.includes('/')) || rawSymbol
  return [
    context.market || context.market_category || '',
    symbol
  ].join(':')
}

export function normalizeMarketContext (context = {}, defaults = {}) {
  const market = normalizeSupportedMarket(context.market || context.market_category || defaults.market || 'Crypto')
  const rawSymbol = String(context.symbol || defaults.symbol || '').trim().toUpperCase()
  return {
    market,
    symbol: market === 'Forex' && rawSymbol ? canonicalizeSupportedSymbol(market, rawSymbol) : rawSymbol,
    exchange_id: market === 'Crypto'
      ? normalizeExchangeId(context.exchange_id || context.exchangeId || defaults.exchange_id || defaults.exchangeId || 'binance')
      : '',
    market_type: normalizeMarketType(
      context.market_type || context.marketType || defaults.market_type || defaults.marketType,
      market
    ),
    instrument_id: String(context.instrument_id || context.instrumentId || defaults.instrument_id || '').trim(),
    settle_currency: String(context.settle_currency || context.settleCurrency || defaults.settle_currency || '').trim().toUpperCase(),
    timeframe: String(context.timeframe || defaults.timeframe || '').trim()
  }
}
