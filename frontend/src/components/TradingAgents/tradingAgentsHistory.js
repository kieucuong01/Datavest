function historyTimestamp (item) {
  return Date.parse(String(item && (item.finished_at || item.generatedAt || item.created_at || item.analysis_date) || '')) || 0
}

function publicTarget (assetKey) {
  const key = String(assetKey || '')
  const [market, symbol] = key.split(':', 2)
  return {
    market: market === 'forex' ? 'Gold' : market === 'crypto' ? 'Crypto' : market,
    symbol: symbol || ''
  }
}

export function publicResearchAssetKeyForTarget (target) {
  const market = String(target && target.market || '').trim().toLowerCase()
  const symbol = String(target && target.symbol || '').trim().toUpperCase()
  if (market === 'crypto') return `crypto:${symbol.includes('/') ? symbol : `${symbol}/USDT`}`
  if (market === 'gold' || market === 'forex') return 'forex:XAUUSD'
  return ''
}

export function mergeTradingAgentsHistory (privateRuns = [], publicReports = [], limit = 100) {
  const account = (Array.isArray(privateRuns) ? privateRuns : []).map(run => ({
    ...run,
    source: 'ACCOUNT_PRIVATE_REPORT'
  }))
  const published = (Array.isArray(publicReports) ? publicReports : []).map(report => {
    const assetKey = String(report && (report.assetKey || report.asset_key) || '')
    const target = publicTarget(assetKey)
    const date = String(report && (report.effectiveDate || report.effective_date) || '')
    return {
      run_id: `public:${assetKey}:${date}`,
      source: 'PUBLIC_RESEARCH_REPORT',
      status: 'succeeded',
      market: target.market,
      symbol: target.symbol,
      analysis_date: date,
      created_at: report.generatedAt || report.generated_at || date,
      finished_at: report.generatedAt || report.generated_at || date,
      public_asset_key: assetKey
    }
  })
  return [...account, ...published]
    .sort((left, right) => historyTimestamp(right) - historyTimestamp(left))
    .slice(0, Math.max(1, Number(limit) || 100))
}
