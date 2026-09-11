function objectOrEmpty (value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function arrayOrEmpty (value) {
  return Array.isArray(value) ? value : []
}

/**
 * Convert the safe AI Assistant history response to the public report shape
 * already consumed by the Smart Insights detail sections.
 */
export function normalizeQuickAnalysisReport (item = {}) {
  const source = objectOrEmpty(item)
  const raw = objectOrEmpty(source.full_result || source.fullResult)
  const input = objectOrEmpty(source.inputData || raw.input_data || raw.inputData)
  const detailedAnalysis = objectOrEmpty(source.detailedAnalysis || raw.detailed_analysis || raw.analysis)
  return {
    id: source.id,
    market: source.market,
    symbol: source.symbol,
    createdAt: source.createdAt || source.created_at || null,
    updatedAt: source.updatedAt || source.updated_at || null,
    status: source.status || source.task_status || 'completed',
    decision: source.decision || raw.final_decision || raw.trader_decision || null,
    confidence: source.confidence ?? null,
    summary: source.summary || raw.summary || raw.reasoning || raw.trader_reasoning || '',
    reasons: arrayOrEmpty(source.reasons || raw.reasons),
    scores: objectOrEmpty(source.scores || raw.scores),
    model: source.model || raw.model || null,
    language: source.language || raw.language || null,
    timeframe: source.timeframe || raw.timeframe || null,
    detailedAnalysis,
    tradingPlan: objectOrEmpty(source.tradingPlan || raw.trading_plan),
    risks: arrayOrEmpty(source.risks || raw.risks),
    marketData: objectOrEmpty(source.marketData || raw.market_data),
    inputData: {
      capturedAt: input.capturedAt || input.captured_at || null,
      priceSource: input.priceSource || input.price_source || null,
      timeframe: input.timeframe || null,
      klineAt: input.klineAt || input.kline_at || null,
      checksum: input.checksum || null,
      components: arrayOrEmpty(input.components)
    },
    indicators: objectOrEmpty(source.indicators || raw.indicators),
    cryptoFactors: objectOrEmpty(source.cryptoFactors || raw.crypto_factors),
    cryptoFactorScore: source.cryptoFactorScore ?? raw.crypto_factor_score ?? null,
    cryptoFactorBreakdown: arrayOrEmpty(source.cryptoFactorBreakdown || raw.crypto_factor_breakdown),
    cryptoFactorSummary: source.cryptoFactorSummary || raw.crypto_factor_summary || '',
    objectiveScore: objectOrEmpty(source.objectiveScore || raw.objective_score),
    scoreBasedDecision: source.scoreBasedDecision || raw.score_based_decision || null,
    consensus: objectOrEmpty(source.consensus || raw.consensus),
    trendOutlook: objectOrEmpty(source.trendOutlook || raw.trend_outlook || raw.trendOutlook),
    trendOutlookSummary: source.trendOutlookSummary || raw.trend_outlook_summary || raw.trendOutlookSummary || '',
    analysisTimeMs: source.analysisTimeMs ?? raw.analysis_time_ms ?? null,
    llmTimeMs: source.llmTimeMs ?? raw.llm_time_ms ?? null,
    dataCollectionTimeMs: source.dataCollectionTimeMs ?? raw.data_collection_time_ms ?? null
  }
}

export function dedupeQuickAnalysisReports (reports = []) {
  const byId = new Map()
  for (const report of reports) {
    if (!report || report.id === undefined || report.id === null) continue
    byId.set(String(report.id), report)
  }
  return [...byId.values()].sort((left, right) => {
    const leftTime = Date.parse(left.createdAt || '') || 0
    const rightTime = Date.parse(right.createdAt || '') || 0
    return rightTime - leftTime
  })
}
