export const UNAVAILABLE = 'UNAVAILABLE'

function textValue (value) {
  return typeof value === 'string' && value.trim() ? value : UNAVAILABLE
}

function countValue (value) {
  const number = Number(value)
  return Number.isFinite(number) && number >= 0 ? number : UNAVAILABLE
}

function stringList (value) {
  return Array.isArray(value)
    ? value.filter(item => typeof item === 'string' && item.trim())
    : []
}

export function buildOverviewModules (overview) {
  if (!overview || overview.status === UNAVAILABLE) {
    return {
      decisionBrief: { available: false, status: UNAVAILABLE },
      pulse: { available: false, status: UNAVAILABLE },
      portfolioImpact: { available: false, status: UNAVAILABLE }
    }
  }

  const summary = overview.summary && typeof overview.summary === 'object' ? overview.summary : {}
  const market = textValue(overview.market).toLowerCase()
  const sources = stringList(summary.sources)
  const metrics = stringList(summary.metrics)
  // Macro remains contextual evidence for the research workspace; it is not a
  // selectable/tradable product market and therefore is absent from the page
  // market filters.
  const pulseAvailable = ['crypto', 'macro', 'vn', 'gold'].includes(market) && (sources.length > 0 || metrics.length > 0)
  const portfolioChanges = Array.isArray(overview.portfolioChanges) ? overview.portfolioChanges : []
  const portfolioState = overview.portfolioState && typeof overview.portfolioState === 'object' ? overview.portfolioState : {}
  const portfolioImpactAvailable = portfolioChanges.length > 0 || Object.keys(portfolioState).length > 0

  return {
    decisionBrief: {
      available: true,
      status: textValue(overview.status),
      asOf: textValue(overview.asOf),
      methodologyVersion: textValue(overview.methodologyVersion),
      directionalModelStatus: textValue(summary.directionalModelStatus),
      evidenceChecksum: textValue(overview.evidenceChecksum),
      sourceCount: countValue(summary.sourceCount),
      metricCount: countValue(summary.metricCount),
      observationCount: countValue(summary.observationCount)
    },
    pulse: pulseAvailable
      ? {
          available: true,
          market,
          sources,
          metrics,
          observationCount: countValue(summary.observationCount)
        }
      : { available: false, status: UNAVAILABLE },
    portfolioImpact: portfolioImpactAvailable
      ? {
          available: true,
          status: textValue(overview.status),
          changeCount: portfolioChanges.length,
          stateAvailable: Object.keys(portfolioState).length > 0
        }
      : { available: false, status: UNAVAILABLE }
  }
}
