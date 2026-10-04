export function reportValidity (report, now = Date.now()) {
  const day = String(report && (report.effectiveDate || report.analysisDate || report.effective_date || report.analysis_date) || '').slice(0, 10)
  const start = Date.parse(`${day}T00:00:00+07:00`)
  if (!Number.isFinite(start)) return { actionable: false, isExpired: false, validUntil: null }
  const weekday = new Date(`${day}T00:00:00Z`).getUTCDay()
  const monday = start - ((weekday + 6) % 7) * 86400000
  const end = monday + 7 * 86400000
  // Compute from the evidence period even for older API payloads. A late
  // publication timestamp must not renew a weekly report's validity.
  return {
 actionable: now >= monday && now < end && report.actionable !== false,
    isExpired: now >= end || report.isExpired === true,
validUntil: new Date(end).toISOString()
}
}
