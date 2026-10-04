export function hosePilotRows (assets = [], watchlist = []) {
  const following = new Set(watchlist.filter(row => String(row.market).toLowerCase() === 'vnstock').map(row => String(row.symbol).toUpperCase()))
  return assets.filter(row => row.market === 'VNStock' && /^[A-Z]{3}$/u.test(row.symbol)).slice(0, 5)
    .map(row => ({ ...row, following: following.has(row.symbol) }))
}

export function hoseResearchNumber (value, unit = '') {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: unit === 'x' ? 2 : 0 }).format(number)}${unit ? ` ${unit}` : ''}`
}
