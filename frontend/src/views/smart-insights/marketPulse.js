export const MARKET_PULSE_TABS = [
  { key: 'macro', vi: 'Vĩ mô', en: 'Macro' },
  { key: 'equities', vi: 'Chứng khoán', en: 'Equities' },
  { key: 'crypto', vi: 'Crypto', en: 'Crypto' }
]

function finite (value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function normalizePulseSeries (series = []) {
  return (Array.isArray(series) ? series : [])
    .map(item => ({
      effectiveAt: String(item && item.effectiveAt || ''),
      value: finite(item && item.value),
      metric: String(item && item.metric || ''),
      symbol: String(item && item.symbol || '')
    }))
    .filter(item => item.effectiveAt && item.value !== null)
    .sort((left, right) => left.effectiveAt.localeCompare(right.effectiveAt))
}

function metricMatches (metric, pattern) {
  return pattern.test(String(metric || ''))
}

function metricsFrom (tab) {
  return Array.isArray(tab && tab.metrics) ? tab.metrics.filter(item => item && finite(item.value) !== null) : []
}

function combinedSeries (...series) {
  return normalizePulseSeries(series.flatMap(item => Array.isArray(item) ? item : []))
}

function uniqueSources (...sourceLists) {
  const seen = new Set()
  return sourceLists.flatMap(list => Array.isArray(list) ? list : []).filter(source => {
    const key = String(source && (source.code || source.name || source.url) || '')
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function groupSeries (series) {
  const grouped = new Map()
  for (const point of normalizePulseSeries(series)) {
    const key = `${point.metric}:${point.symbol}`
    if (!grouped.has(key)) grouped.set(key, [])
    grouped.get(key).push(point)
  }
  return Array.from(grouped.entries()).map(([key, points]) => ({ key, points }))
}

function tabModel (key, tab, options = {}) {
  const series = normalizePulseSeries(options.series || tab.series || [])
  return {
    key,
    status: tab.status || 'UNAVAILABLE',
    sources: Array.isArray(tab.sources) ? tab.sources : [],
    metrics: options.metrics || metricsFrom(tab),
    series,
    seriesGroups: groupSeries(series),
    groups: Array.isArray(tab.groups) ? tab.groups : [],
    fearGreed: options.fearGreed || tab.fearGreed || null,
    etfFlows: options.etfFlows || tab.etfFlows || null,
    whaleFlows: options.whaleFlows || tab.whaleFlows || null,
    fundFlows: options.fundFlows || tab.fundFlows || null,
    halving: options.halving || tab.halving || null,
    priceHistory: options.priceHistory || tab.priceHistory || null,
    derivatives: options.derivatives || tab.derivatives || null,
    latest: series.length ? series[series.length - 1] : null
  }
}

export function buildPulsePanel (pulse = {}, key = 'overview') {
  const tabs = pulse && pulse.tabs ? pulse.tabs : {}
  const shared = tabs.sentimentDerivatives || {}
  if (key === 'crypto') {
    const flows = tabs.flows || {}
    const cycle = tabs.cycle || {}
    const onchain = tabs.onchain || {}
    const metrics = [
      ...metricsFrom(flows),
      ...metricsFrom(shared),
      ...metricsFrom(cycle),
      ...metricsFrom(onchain)
    ]
    const tab = {
      status: metrics.length ? 'AVAILABLE' : 'UNAVAILABLE',
      sources: uniqueSources(flows.sources, shared.sources, cycle.sources, onchain.sources)
    }
    const etf = flows.etfFlows || {}
    const whaleFlows = flows.whaleFlows || null
    const fearGreed = shared.fearGreed || null
    return tabModel(key, tab, {
      metrics,
      fearGreed,
      etfFlows: etf,
      whaleFlows,
      derivatives: shared.derivatives || null,
      series: combinedSeries(
        etf.series,
        whaleFlows && whaleFlows.series,
        fearGreed && fearGreed.series,
        shared.series,
        cycle.series,
        onchain.series
      )
    })
  }
  if (key === 'macro' || key === 'equities') return tabModel(key, tabs[key] || {})
  if (key === 'overview') {
    const tab = tabs.overview || {}
    const etf = tab.etfFlows || {}
    const fund = tab.fundFlows || {}
    return tabModel(key, tab, {
      fearGreed: tab.fearGreed || null,
      etfFlows: etf,
      fundFlows: fund,
      series: combinedSeries((tab.fearGreed || {}).series, etf.series, fund.series)
    })
  }
  if (key === 'flows') {
    const tab = tabs.flows || {}
    const etf = tab.etfFlows || {}
    const whaleFlows = tab.whaleFlows || null
    return tabModel(key, tab, {
      etfFlows: etf,
      whaleFlows,
      series: combinedSeries(etf.series, whaleFlows && whaleFlows.series)
    })
  }
  if (key === 'sentiment') {
    const fearGreed = shared.fearGreed || {}
    const metrics = metricsFrom(shared).filter(item => metricMatches(item.metric, /fear|greed|sentiment/iu))
    return tabModel(key, shared, {
      fearGreed,
      metrics,
      series: combinedSeries(fearGreed.series, metrics)
    })
  }
  if (key === 'derivatives') {
    const metrics = metricsFrom(shared).filter(item => metricMatches(item.metric, /derivative|funding|margin|liquidation|open[_ ]?interest/iu))
    const derivativeSeries = (shared.series || []).filter(item => metricMatches(item && item.metric, /derivative|funding|margin|liquidation|open[_ ]?interest/iu))
    return tabModel(key, shared, {
      metrics,
      series: derivativeSeries,
      derivatives: shared.derivatives || null
    })
  }
  const tab = tabs[key] || {}
  return tabModel(key, tab)
}

export function pulseTabLabel (tab, locale = 'vi') {
  return tab && tab[locale] ? tab[locale] : tab && tab.key
}

export default MARKET_PULSE_TABS
