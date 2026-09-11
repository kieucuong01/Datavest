const valid = p => p && p.value !== null && p.value !== undefined && p.value !== '' && Number.isFinite(Number(p.value))

export function latestMetric (rows, metric, symbol = 'BTC') {
  return rows.filter(p => valid(p) && p.metric === metric && (!p.symbol || p.symbol === symbol))
    .sort((a, b) => String(a.effectiveAt).localeCompare(String(b.effectiveAt)) || Number(a.source === 'bitview-onchain') - Number(b.source === 'bitview-onchain')).pop() || null
}

export function chartEntries (rows, symbol = 'BTC') {
  const groups = new Map()
  for (const point of rows) {
    if (!valid(point) || (point.symbol && point.symbol !== symbol)) continue
    const key = `${point.metric}:${point.symbol || 'ALL'}:${point.source}:${point.dimension || ''}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(point)
  }
  return Array.from(groups, ([key, points]) => ({
    key,
    metric: points[0].metric,
    symbol: points[0].symbol,
    source: points[0].source,
    dimension: points[0].dimension,
    points: points.sort((a, b) => String(a.effectiveAt).localeCompare(String(b.effectiveAt))).slice(-365)
  }))
}
