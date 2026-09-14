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

function guestResearchInDevelopment (item) {
  return canonicalOpinionMarket(item && item.market) === 'vn' && canonicalOpinionSymbol(item && (item.symbol || item.sym)) === 'VNINDEX'
}

const GUEST_PUBLIC_ASSETS = Object.freeze([
  { market: 'Crypto', symbol: 'BTC/USDT', name: 'Bitcoin' },
  { market: 'Crypto', symbol: 'SOL/USDT', name: 'Solana' },
  { market: 'Crypto', symbol: 'LINK/USDT', name: 'Chainlink' },
  { market: 'Forex', symbol: 'XAUUSD', name: 'Gold' }
])

export function publicResearchAssetKey (item) {
  const market = cleanSymbol(item && item.market)
  const symbol = cleanSymbol(item && (item.symbol || item.sym))
  if (market === 'CRYPTO' && canonicalOpinionSymbol(symbol) === 'BTC') return 'crypto:BTC/USDT'
  if (market === 'CRYPTO' && canonicalOpinionSymbol(symbol) === 'SOL') return 'crypto:SOL/USDT'
  if (market === 'CRYPTO' && canonicalOpinionSymbol(symbol) === 'LINK') return 'crypto:LINK/USDT'
  if ((market === 'FOREX' || market === 'GOLD') && canonicalOpinionSymbol(symbol) === 'XAU') return 'forex:XAUUSD'
  return ''
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
      publicAssetKey: item.researchInDevelopment ? '' : publicResearchAssetKey(item),
      symbol: item.symbol || item.sym,
      displaySymbol: canonicalOpinionSymbol(item.symbol || item.sym),
      market: item.market,
      name: item.name || item.symbol || item.sym,
      watchlistItem: item,
      publicCommon: false,
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
  const candidates = [...(Array.isArray(assets) ? assets : []), ...sharedAnalyses]
  const sourceAssets = GUEST_PUBLIC_ASSETS.map(defaultAsset => {
    const defaultIdentity = identity(defaultAsset)
    return candidates.find(item => identity(item) === defaultIdentity) || defaultAsset
  })
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
      publicAssetKey: publicResearchAssetKey(item),
      symbol: item.symbol || item.sym,
      displaySymbol: canonicalOpinionSymbol(item.symbol || item.sym),
      market: item.market,
      name: item.name || item.displaySymbol || item.symbol || item.sym,
      watchlistItem: null,
      publicCommon: true,
      report,
      shared: Boolean(report),
      researchInDevelopment: guestResearchInDevelopment(item),
      monitor: null,
      dataFreshness: report ? 'UNKNOWN' : 'UNAVAILABLE',
      analysisStatus: report ? 'AVAILABLE' : 'UNAVAILABLE'
    }
  })
}

export function buildAccountOpinionRows (watchlist = [], analyses = [], asOf = null) {
  const rows = buildSharedOpinionRows([], analyses, asOf)
  const index = new Map(rows.map(row => [row.id, row]))

  for (const row of buildWatchlistOpinionRows(watchlist, analyses, asOf)) {
    const existing = index.get(row.id)
    if (existing) {
      rows[rows.indexOf(existing)] = { ...row, publicCommon: true }
    } else {
      rows.push(row)
    }
    index.set(row.id, row)
  }

  return rows
}

export function applySharedResearchStates (rows = [], states = []) {
  const indexed = new Map()
  for (const state of Array.isArray(states) ? states : []) {
    const key = String(state && state.assetKey || '')
    const kind = String(state && state.reportKind || '').toLowerCase()
    if (key && kind) indexed.set(`${key}:${kind}`, state)
  }
  return (Array.isArray(rows) ? rows : []).map(row => {
    const assetKey = row.publicAssetKey || publicResearchAssetKey(row) || ''
    const deepState = indexed.get(`${assetKey}:deep`) || null
    return {
      ...row,
      publicAssetKey: assetKey,
      sharedResearchAssetKey: assetKey,
      publicCommon: Boolean((deepState || {}).scope === 'public_common') || Boolean(row.publicCommon),
      deepState,
      dataFreshness: deepState && deepState.status === 'pending' ? 'PENDING' : row.dataFreshness,
      analysisStatus: deepState && deepState.status ? String(deepState.status).toUpperCase() : 'UNAVAILABLE'
    }
  })
}

function publicDeepReport (item) {
  const source = objectOrEmpty(item)
  if (String(source.reportKind || source.report_kind || '').toLowerCase() !== 'deep') return null
  const sections = Array.isArray(source.sections) ? source.sections : []
  const sectionItems = title => sections
    .filter(section => String(section && section.title || '').toLowerCase() === title)
    .flatMap(section => Array.isArray(section && section.items) ? section.items : [])
    .map(textOrEmpty)
    .filter(Boolean)
    .slice(0, 8)
  const confidence = Number(source.confidence)
  return {
    id: `public:${source.assetKey || source.asset_key}:${source.effectiveDate || source.effective_date || ''}`,
    source: 'PUBLIC_RESEARCH_REPORT',
    scope: 'PUBLIC_COMMON_ASSETS',
    status: 'completed',
    decision: normalizeSharedDecision(source.decision),
    confidence: Number.isFinite(confidence) ? confidence : null,
    summary: textOrEmpty(source.summary),
    reasons: sectionItems('luận điểm'),
    risks: sectionItems('rủi ro'),
    analysisDate: source.effectiveDate || source.effective_date || null,
    createdAt: source.generatedAt || source.generated_at || null,
    updatedAt: source.generatedAt || source.generated_at || null,
    inputData: { capturedAt: source.generatedAt || source.generated_at || null, components: [] }
  }
}

export function applyPublicDeepReports (rows = [], reports = []) {
  const indexed = new Map()
  for (const item of Array.isArray(reports) ? reports : []) {
    const key = String(item && (item.assetKey || item.asset_key) || '')
    const report = publicDeepReport(item)
    if (key && report) indexed.set(key, { report, isFallback: Boolean(item && item.isFallback) })
  }
  return (Array.isArray(rows) ? rows : []).map(row => {
    const publicReport = indexed.get(row.publicAssetKey)
    if (!publicReport) return row
    return {
      ...row,
      deepState: { status: 'completed', report: publicReport.report, scope: 'public_common', canCreate: false },
      dataFreshness: publicReport.isFallback ? 'STALE' : 'UNKNOWN',
      analysisStatus: publicReport.isFallback ? 'STALE' : 'AVAILABLE'
    }
  })
}

export default buildWatchlistOpinionRows
