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

function objectOrEmpty (value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function textOrEmpty (value) {
  return typeof value === 'string' ? value.trim().slice(0, 2000) : ''
}

function normalizeSharedDecision (value) {
  const text = cleanSymbol(value).replace(/[ -]+/gu, '_')
  if (['BUY', 'STRONG_BUY', 'POSITIVE', 'BULLISH'].includes(text)) return 'BUY'
  if (['SELL', 'STRONG_SELL', 'NEGATIVE', 'BEARISH'].includes(text)) return 'SELL'
  if (['HOLD', 'NEUTRAL', 'WATCH', 'EVIDENCE_ONLY'].includes(text)) return 'HOLD'
  return null
}

function sharedReasons (rationale) {
  const source = objectOrEmpty(rationale)
  const values = source.reasons || source.arguments || source.factors
  if (!Array.isArray(values)) return []
  return values.map(textOrEmpty).filter(Boolean).slice(0, 8)
}

function sharedSummary (analysis, rationale) {
  const source = objectOrEmpty(rationale)
  return [
    textOrEmpty(analysis.explanation),
    textOrEmpty(source.summary),
    textOrEmpty(source.text),
    textOrEmpty(source.reason),
    textOrEmpty(source.warning)
  ].find(Boolean) || ''
}

export function buildSharedOpinionReport (analysis, asOf = null) {
  const source = objectOrEmpty(analysis)
  if (source.report) return null
  const dataClass = cleanSymbol(source.dataClass)
  if (dataClass && dataClass !== 'LIVE') return null
  const rationale = objectOrEmpty(source.rationale)
  const hasOpinionPayload = Boolean(
    source.stance || source.explanation || source.score !== undefined || source.confidence !== undefined || Object.keys(rationale).length
  )
  if (!hasOpinionPayload) return null

  const numeric = value => {
    if (value === null || value === undefined || value === '') return null
    const number = Number(value)
    return Number.isFinite(number) ? number : null
  }
  const decision = normalizeSharedDecision(source.stance)
  return {
    id: source.id || null,
    market: source.market,
    symbol: source.symbol,
    source: 'PUBLIC_COMMON_SNAPSHOT',
    scope: 'PUBLIC_COMMON_ASSETS',
    status: 'completed',
    decision,
    confidence: numeric(source.confidence),
    summary: sharedSummary(source, rationale),
    reasons: sharedReasons(rationale),
    score: numeric(source.score),
    analysisDate: asOf,
    createdAt: asOf,
    updatedAt: asOf,
    inputData: { capturedAt: asOf, components: [] }
  }
}

export function buildWatchlistOpinionRows (watchlist = [], analyses = [], asOf = null) {
  const indexed = new Map()
  for (const analysis of Array.isArray(analyses) ? analyses : []) {
    const key = identity(analysis)
    if (key !== ':') indexed.set(key, analysis || {})
  }

  return (Array.isArray(watchlist) ? watchlist : []).map(item => {
    const key = identity(item)
    const analysis = indexed.get(key) || {}
    const sharedReport = buildSharedOpinionReport(analysis, asOf)
    const report = analysis.report || sharedReport
    return {
      id: key,
      symbol: item.symbol || item.sym,
      displaySymbol: canonicalOpinionSymbol(item.symbol || item.sym),
      market: item.market,
      name: item.name || item.symbol || item.sym,
      watchlistItem: item,
      report,
      shared: Boolean(sharedReport && !analysis.report),
      monitor: analysis && analysis.monitor ? analysis.monitor : null,
      dataFreshness: analysis && analysis.dataFreshness ? analysis.dataFreshness : (report ? 'UNKNOWN' : 'UNAVAILABLE'),
      analysisStatus: analysis && analysis.analysisStatus ? analysis.analysisStatus : (report ? 'AVAILABLE' : 'UNAVAILABLE')
    }
  })
}

export function buildSharedOpinionRows (assets = [], analyses = [], asOf = null) {
  const sharedAnalyses = Array.isArray(analyses)
    ? analyses.filter(analysis => analysis && typeof analysis === 'object' && !analysis.report)
    : []
  const sourceAssets = Array.isArray(assets) && assets.length
    ? assets
    : sharedAnalyses
  const indexed = new Map()
  for (const analysis of sharedAnalyses) {
    const key = identity(analysis)
    if (key !== ':') indexed.set(key, analysis || {})
  }

  return sourceAssets.map(item => {
    const key = identity(item)
    const analysis = indexed.get(key) || {}
    const report = buildSharedOpinionReport(analysis, asOf)
    return {
      id: key,
      symbol: item.symbol || item.sym,
      displaySymbol: canonicalOpinionSymbol(item.symbol || item.sym),
      market: item.market,
      name: item.name || item.displaySymbol || item.symbol || item.sym,
      watchlistItem: null,
      report,
      shared: Boolean(report),
      monitor: null,
      dataFreshness: report ? 'UNKNOWN' : 'UNAVAILABLE',
      analysisStatus: report ? 'AVAILABLE' : 'UNAVAILABLE'
    }
  })
}

export default buildWatchlistOpinionRows
