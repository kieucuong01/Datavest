function cleanSymbol (value) {
  return String(value || '').trim().toUpperCase()
}

export function canonicalOpinionSymbol (value) {
  const symbol = cleanSymbol(value)
  if (symbol === 'XAUUSD' || symbol === 'GOLD') return 'XAU'
  return symbol.replace(/[/:-](USDT|USD)$/u, '')
}

export function canonicalOpinionMarket (value) {
  const normalized = cleanSymbol(value)
  return ({
    CRYPTO: 'crypto',
    VNSTOCK: 'vn',
    USSTOCK: 'us',
    FOREX: 'gold',
    GOLD: 'gold'
  })[normalized] || String(value || '').trim().toLowerCase()
}

function identity (item) {
  return `${canonicalOpinionMarket(item && item.market)}:${canonicalOpinionSymbol(item && (item.symbol || item.sym))}`
}

export function buildWatchlistOpinionRows (watchlist = [], analyses = []) {
  const indexed = new Map()
  for (const analysis of Array.isArray(analyses) ? analyses : []) {
    const key = identity(analysis)
    if (key !== ':') indexed.set(key, analysis || {})
  }

  return (Array.isArray(watchlist) ? watchlist : []).map(item => {
    const key = identity(item)
    const analysis = indexed.get(key) || {}
    const report = analysis.report || null
    return {
      id: key,
      symbol: item.symbol || item.sym,
      displaySymbol: canonicalOpinionSymbol(item.symbol || item.sym),
      market: item.market,
      name: item.name || item.symbol || item.sym,
      watchlistItem: item,
      report,
      monitor: analysis && analysis.monitor ? analysis.monitor : null,
      dataFreshness: analysis && analysis.dataFreshness ? analysis.dataFreshness : (report ? 'UNKNOWN' : 'UNAVAILABLE'),
      analysisStatus: analysis && analysis.analysisStatus ? analysis.analysisStatus : (report ? 'AVAILABLE' : 'UNAVAILABLE')
    }
  })
}

export default buildWatchlistOpinionRows
