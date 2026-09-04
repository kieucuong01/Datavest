function objectOrEmpty (value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

export function buildOpinionPresentation (row) {
  const source = objectOrEmpty(row)
  const report = objectOrEmpty(source.report)
  const inputData = objectOrEmpty(report.inputData)
  const monitor = objectOrEmpty(source.monitor)
  const status = String(source.analysisStatus || (source.report ? 'AVAILABLE' : 'UNAVAILABLE')).toUpperCase()
  return {
    status,
    freshness: String(source.dataFreshness || (source.report ? 'UNKNOWN' : 'UNAVAILABLE')).toUpperCase(),
    monitorState: String(monitor.state || 'MISSING').toUpperCase(),
    capturedAt: inputData.capturedAt || null,
    nextRunAt: monitor.nextRunAt || null,
    needsAssistant: !source.report
  }
}

export default buildOpinionPresentation
