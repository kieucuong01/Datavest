export const STRATEGY_LOG_FILTERS = Object.freeze([
  { value: 'all', icon: 'bars' },
  { value: 'trade', icon: 'transaction' },
  { value: 'signal', icon: 'notification' },
  { value: 'warning', icon: 'exclamation-circle' },
  { value: 'error', icon: 'warning' }
])

export const normalizeStrategyLogLevel = level => {
  const normalized = String(level || 'info').trim().toLowerCase()
  return normalized === 'warn' ? 'warning' : normalized
}

export const strategyLogLevelKey = level => {
  const normalized = normalizeStrategyLogLevel(level)
  return `trading-assistant.logs.level.${normalized}`
}
