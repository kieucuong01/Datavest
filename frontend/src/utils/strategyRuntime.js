const asObject = value => {
  if (value && typeof value === 'object' && !Array.isArray(value)) return value
  if (typeof value !== 'string' || !value.trim()) return {}
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch (error) {
    return {}
  }
}

export const normalizeTimestampMilliseconds = value => {
  if (value === null || value === undefined || value === '') return 0
  if (typeof value === 'number' || /^\d+(?:\.\d+)?$/.test(String(value).trim())) {
    const numeric = Number(value)
    if (!Number.isFinite(numeric)) return 0
    return numeric < 100000000000 ? numeric * 1000 : numeric
  }
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export const strategyTradingConfig = strategy => asObject(strategy && strategy.trading_config)

export const strategyExchangeId = strategy => {
  const exchange = asObject(strategy && strategy.exchange_config)
  const trading = strategyTradingConfig(strategy)
  return String(
    exchange.exchange_id ||
    exchange.exchangeId ||
    trading.exchange_id ||
    trading.exchangeId ||
    (strategy && (strategy.exchange_id || strategy.exchangeId)) ||
    ''
  ).trim().toLowerCase()
}

export const strategyExecutionMode = strategy => {
  const config = strategyTradingConfig(strategy)
  const mode = String((strategy && strategy.execution_mode) || config.execution_mode || '').trim().toLowerCase()
  return mode === 'live' ? 'live' : 'signal'
}

export const strategySymbol = strategy => {
  const config = strategyTradingConfig(strategy)
  // The strategy row is the deployment authority. Older sources may retain an
  // IDE last-run default in trading_config.symbol (for example BTC/USDT on a
  // USStock:SPY source), so the nested runtime hint must only be a fallback.
  const direct = String((strategy && strategy.symbol) || config.symbol || '').trim()
  if (direct) return direct
  return ''
}

export const strategyCapital = strategy => {
  const config = strategyTradingConfig(strategy)
  const candidates = [
    strategy && strategy.initial_capital,
    config.initial_capital,
    config.initialCapital
  ]
  for (const value of candidates) {
    const number = Number(value)
    if (Number.isFinite(number) && number > 0) return number
  }
  return 0
}

export const strategyLeverage = strategy => {
  const config = strategyTradingConfig(strategy)
  const marketType = String(config.market_type || (strategy && strategy.market_type) || '').trim().toLowerCase()
  if (marketType === 'spot') return 1
  const candidates = [config.leverage, strategy && strategy.leverage]
  for (const value of candidates) {
    const number = Number(value)
    if (Number.isFinite(number) && number >= 1) return number
  }
  return 1
}

export const strategyQuoteCurrency = strategy => {
  const config = strategyTradingConfig(strategy)
  const explicit = String(
    config.quote_currency ||
    config.quoteCurrency ||
    (strategy && (strategy.quote_currency || strategy.quoteCurrency)) ||
    ''
  ).trim().toUpperCase()
  if (explicit) return explicit

  const rawSymbol = strategySymbol(strategy)
  const instrument = rawSymbol.replace(/^[^:]+:/, '').replace(/@(spot|swap|future|futures)$/i, '')
  if (instrument.includes('/')) {
    const quote = instrument.split('/')[1]
    if (quote) return quote.trim().toUpperCase()
  }
  if (/^USStock:/i.test(rawSymbol)) return 'USD'
  if (/^VNStock:/i.test(rawSymbol)) return 'VND'
  if (/^Forex:/i.test(rawSymbol)) return 'USD'
  return 'USDT'
}

export const summarizeStrategyPerformance = ({ strategy, curve = [], trades = [] } = {}) => {
  const capital = strategyCapital(strategy)
  const values = (Array.isArray(curve) ? curve : [])
    .map(item => Number(item && (item.equity != null ? item.equity : item.value)))
    .filter(Number.isFinite)
  const fallbackPnl = Number(strategy && strategy.total_pnl)
  const latestEquity = values.length
    ? values[values.length - 1]
    : capital + (Number.isFinite(fallbackPnl) ? fallbackPnl : 0)
  const netPnl = capital > 0 ? latestEquity - capital : 0
  const totalReturn = capital > 0 ? netPnl / capital : 0

  let peak = capital > 0 ? capital : (values.length ? values[0] : 0)
  let maxDrawdown = 0
  values.forEach(value => {
    if (value > peak) peak = value
    if (peak > 0) maxDrawdown = Math.min(maxDrawdown, (value - peak) / peak)
  })

  const settledTrades = (Array.isArray(trades) ? trades : []).filter(trade => {
    const type = String(trade && trade.type || '').toLowerCase()
    return !type.startsWith('open') &&
      !type.startsWith('add') &&
      trade && trade.profit != null && trade.profit !== '' &&
      Number.isFinite(Number(trade.profit))
  })
  const wins = settledTrades.filter(trade => Number(trade.profit) > 0).length

  return {
    capital,
    latestEquity,
    netPnl,
    totalReturn,
    maxDrawdown,
    winRate: settledTrades.length ? wins / settledTrades.length : 0,
    wins,
    completedTrades: settledTrades.length
  }
}

export const strategyLastActivity = strategy => {
  const config = strategyTradingConfig(strategy)
  return config.last_execution_time || config.last_signal_time || (strategy && strategy.updated_at) || (strategy && strategy.created_at) || ''
}

export const strategyLastActivityTimestamp = strategy => normalizeTimestampMilliseconds(strategyLastActivity(strategy))

export const strategyRuntimeSummary = strategies => {
  const list = Array.isArray(strategies) ? strategies : []
  return list.reduce((summary, strategy) => {
    const running = String((strategy && strategy.status) || '').trim().toLowerCase() === 'running'
    const executionMode = strategyExecutionMode(strategy)
    summary.total += 1
    if (running) summary.running += 1
    if (running && executionMode === 'live') summary.runningLive += 1
    if (running && executionMode === 'signal') summary.runningSignal += 1
    summary.totalPnl += Number((strategy && strategy.total_pnl) || 0)
    summary.totalCapital += Number((strategy && strategy.initial_capital) || 0)
    return summary
  }, {
    total: 0,
    running: 0,
    runningLive: 0,
    runningSignal: 0,
    totalPnl: 0,
    totalCapital: 0
  })
}

export const filterAndSortStrategies = (strategies, filters = {}) => {
  const keyword = String(filters.keyword || '').trim().toLowerCase()
  const status = String(filters.status || 'all').trim().toLowerCase()
  const executionMode = String(filters.executionMode || 'all').trim().toLowerCase()
  return (Array.isArray(strategies) ? strategies : [])
    .filter(strategy => {
      const rowStatus = String((strategy && strategy.status) || '').trim().toLowerCase() || 'stopped'
      if (status !== 'all' && rowStatus !== status) return false
      const rowExecutionMode = strategyExecutionMode(strategy)
      if (executionMode !== 'all' && rowExecutionMode !== executionMode) return false
      if (!keyword) return true
      const config = strategyTradingConfig(strategy)
      const haystack = [
        strategy && strategy.id,
        strategy && strategy.strategy_name,
        strategySymbol(strategy),
        config.timeframe,
        strategyExchangeId(strategy)
      ].map(item => String(item || '').toLowerCase()).join(' ')
      return haystack.includes(keyword)
    })
    .sort((left, right) => {
      const leftRunning = String((left && left.status) || '').trim().toLowerCase() === 'running' ? 1 : 0
      const rightRunning = String((right && right.status) || '').trim().toLowerCase() === 'running' ? 1 : 0
      if (leftRunning !== rightRunning) return rightRunning - leftRunning
      const activityDiff = strategyLastActivityTimestamp(right) - strategyLastActivityTimestamp(left)
      if (activityDiff) return activityDiff
      return Number((right && right.id) || 0) - Number((left && left.id) || 0)
    })
}
