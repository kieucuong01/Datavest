function objectOrEmpty (value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function arrayOrEmpty (value) {
  return Array.isArray(value) ? value : []
}

function inputDataOrEmpty (value) {
  const source = objectOrEmpty(value)
  return {
    capturedAt: source.capturedAt || null,
    priceSource: source.priceSource || null,
    timeframe: source.timeframe || null,
    klineAt: source.klineAt || null,
    checksum: source.checksum || null,
    components: arrayOrEmpty(source.components)
  }
}

export function buildAssetAnalysisDetails (report) {
  const source = objectOrEmpty(report)
  return {
    detailedAnalysis: objectOrEmpty(source.detailedAnalysis),
    tradingPlan: objectOrEmpty(source.tradingPlan),
    risks: arrayOrEmpty(source.risks),
    marketData: objectOrEmpty(source.marketData),
    indicators: objectOrEmpty(source.indicators),
    cryptoFactors: objectOrEmpty(source.cryptoFactors),
    cryptoFactorScore: source.cryptoFactorScore,
    cryptoFactorBreakdown: arrayOrEmpty(source.cryptoFactorBreakdown),
    cryptoFactorSummary: String(source.cryptoFactorSummary || ''),
    consensus: objectOrEmpty(source.consensus),
    trendOutlook: objectOrEmpty(source.trendOutlook),
    trendOutlookSummary: String(source.trendOutlookSummary || ''),
    inputData: inputDataOrEmpty(source.inputData),
    timeframe: source.timeframe,
    model: source.model,
    analysisTimeMs: source.analysisTimeMs,
    llmTimeMs: source.llmTimeMs,
    dataCollectionTimeMs: source.dataCollectionTimeMs
  }
}

export function canShowTradingPlan (report) {
  const source = objectOrEmpty(report)
  const plan = objectOrEmpty(source.tradingPlan)
  const hasLevels = ['entry_price', 'entryPrice', 'stop_loss', 'stopLoss', 'take_profit', 'takeProfit'].some(key => plan[key] !== undefined && plan[key] !== null && plan[key] !== '')
  const confidence = Number(source.confidence)
  return hasLevels && ['BUY', 'SELL'].includes(String(source.decision || '').toUpperCase()) && Number.isFinite(confidence) && confidence >= 60
}

export default buildAssetAnalysisDetails
