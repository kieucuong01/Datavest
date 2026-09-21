export function hasScore (value) {
  return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
}

export function hosePriceLabel (value) {
  if (value === null || value === undefined || value === '') return '--'
  const price = Number(value)
  if (!Number.isFinite(price)) return '--'
  return `${price.toLocaleString('vi-VN', { maximumFractionDigits: 2 })} VND`
}

export function hoseScoreLabel (score, language = 'vi-VN') {
  if (!hasScore(score)) return String(language).toLowerCase().startsWith('vi') ? 'Không đủ dữ liệu' : 'Insufficient data'
  return String(score)
}

export function hoseLatencyLabel (provenance, language = 'vi-VN') {
  const price = provenance && provenance.price ? provenance.price : {}
  const vi = String(language).toLowerCase().startsWith('vi')
  if (price.latencyClass === 'eod') return 'EOD'
  if (price.latencyClass === 'real_time') return vi ? 'Thời gian thực' : 'Real-time'
  if (price.latencyClass === 'delayed') {
    const delay = Number(price.delayMinutes)
    return Number.isFinite(delay) && price.delayMinutes != null
      ? (vi ? `Trễ ${delay} phút` : `Delayed ${delay} min`)
      : (vi ? 'Dữ liệu trễ' : 'Delayed')
  }
  return vi ? 'Chưa xác định' : 'Unknown'
}

export function hoseCoverageRows (coverage) {
  return Object.entries(coverage || {}).map(([key, entry]) => ({
    key,
    status: entry && entry.status ? entry.status : 'unknown',
    reason: entry && entry.reason ? entry.reason : null
  }))
}
