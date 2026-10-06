export function vietnamDay (now = new Date()) { return new Date(now.getTime() + 7 * 3600000).toISOString().slice(0, 10) }
export function filterHistory (points, timeframe, today = vietnamDay()) {
  const day = new Date(today + 'T00:00:00Z')
  let start = ''
  if (timeframe === '1w' || timeframe === '1m') { day.setUTCDate(day.getUTCDate() - (timeframe === '1w' ? 7 : 30)); start = day.toISOString().slice(0, 10) }
  if (timeframe === 'ytd') start = today.slice(0, 4) + '-01-01'
  return points.filter(point => point.day >= start && point.day < today)
}
export function navChartOptions (points) {
  return { tooltip: { trigger: 'axis' }, grid: { left: 65, right: 25, top: 20, bottom: 40 }, xAxis: { type: 'category', data: points.map(p => p.day) }, yAxis: { type: 'value', scale: true }, series: [{ name: 'NAV', type: 'line', connectNulls: false, data: points.map(p => p.nav === null || p.nav === undefined ? null : Number(p.nav)), showSymbol: true }] }
}
