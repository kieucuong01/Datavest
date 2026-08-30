import { canonicalOpinionMarket, canonicalOpinionSymbol } from './watchlistOpinions.js'

function parseObject (value, fallback = {}) {
  if (value && typeof value === 'object') return value
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return parsed && typeof parsed === 'object' ? parsed : fallback
    } catch (error) {
      return fallback
    }
  }
  return fallback
}

function monitorIdentity (monitor) {
  const config = parseObject(monitor && monitor.config)
  const market = canonicalOpinionMarket(config.market || (monitor && monitor.market))
  const symbol = canonicalOpinionSymbol(config.symbol || (monitor && monitor.symbol))
  return market && symbol ? `${market}:${symbol}` : ''
}

function timestampValue (value) {
  const time = Date.parse(value || '')
  return Number.isFinite(time) ? time : 0
}

function hasResult (monitor) {
  const result = parseObject(monitor && monitor.last_result)
  return Boolean(result.success || result.analysis || (Array.isArray(result.position_analyses) && result.position_analyses.length))
}

function shouldReplace (current, candidate) {
  if (!current) return true
  if (hasResult(candidate) !== hasResult(current)) return hasResult(candidate)
  const candidateTime = timestampValue(candidate.last_run_at || candidate.updated_at || candidate.created_at)
  const currentTime = timestampValue(current.last_run_at || current.updated_at || current.created_at)
  if (candidateTime !== currentTime) return candidateTime > currentTime
  return Number(candidate.id || 0) > Number(current.id || 0)
}

export function buildScheduledAnalysisIndex (monitors = []) {
  const index = {}
  for (const monitor of Array.isArray(monitors) ? monitors : []) {
    const identity = monitorIdentity(monitor)
    if (!identity || shouldReplace(index[identity], monitor)) {
      index[identity] = {
        ...monitor,
        config: parseObject(monitor && monitor.config),
        last_result: parseObject(monitor && monitor.last_result)
      }
    }
  }
  return index
}

export function scheduledAnalysisResult (monitor) {
  const result = parseObject(monitor && monitor.last_result)
  return Object.keys(result).length ? result : null
}

export function scheduledAnalysisIdentity (monitor) {
  return monitorIdentity(monitor)
}

export default buildScheduledAnalysisIndex
