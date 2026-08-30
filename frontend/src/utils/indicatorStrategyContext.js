export function resolveIndicatorStrategyContext (context = {}, route = {}, config = {}) {
  const market = String(context.market || route.market || config.market_category || config.marketCategory || '').trim()
  const symbol = String(context.symbol || route.symbol || config.symbol || '').trim()
  const exchangeId = String(context.exchange_id || route.exchange_id || config.exchange_id || '').trim().toLowerCase()
  const requestedMarketType = String(context.market_type || route.market_type || config.market_type || 'spot').trim().toLowerCase()
  const marketType = requestedMarketType === 'swap' ? 'swap' : 'spot'
  const timeframe = String(context.timeframe || route.timeframe || config.timeframe || '').trim()
  let instrument = String(context.instrument_id || route.instrument_id || '').trim()

  if (!instrument && symbol) {
    if (/^(?:VNStock|Crypto|Forex|USStock):/i.test(symbol)) {
      instrument = symbol
    } else if (market.toLowerCase() === 'crypto') {
      const suffix = symbol.includes('@')
        ? ''
        : `@${exchangeId ? `${exchangeId}:` : ''}${marketType}`
      instrument = `Crypto:${symbol}${suffix}`
    } else {
      instrument = market ? `${market}:${symbol}` : symbol
    }
  }

  return {
    market,
    symbol,
    exchangeId,
    marketType,
    timeframe,
    instrument
  }
}
