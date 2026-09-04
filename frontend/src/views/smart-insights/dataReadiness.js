import { vietnamDateKey } from '../../utils/vietnamTime.js'

export function vietnamToday (now = new Date()) {
  return vietnamDateKey(now)
}

export function isCurrentRequest (requestId, activeRequestId) {
  return requestId === activeRequestId
}

export function summarizeReadiness (sections = [], sourceRows = [], loading = false) {
  if (loading) return { status: 'LOADING', issues: [], fetchedAt: '' }

  const normalized = sections
    .filter(Boolean)
    .map(section => String(section.freshness || section.status || '').toUpperCase())
  const sourceIssues = sourceRows.filter(row => {
    const freshness = String(row && row.freshness || '').toUpperCase()
    const runStatus = String(row && row.lastRun && row.lastRun.status || '').toUpperCase()
    return ['STALE', 'UNAVAILABLE', 'FAILED', 'ERROR'].includes(freshness) || ['FAILED', 'ERROR'].includes(runStatus)
  })
  const issues = sourceIssues.map(row => ({
    key: row.code || row.name || 'source',
    label: row.name || row.code || 'Source',
    status: String(row.freshness || row.lastRun && row.lastRun.status || 'UNAVAILABLE').toUpperCase()
  }))

  if (!normalized.length || normalized.every(value => value === 'UNAVAILABLE')) {
    return { status: 'UNAVAILABLE', issues, fetchedAt: '' }
  }
  if (normalized.some(value => ['PARTIAL', 'STALE', 'UNAVAILABLE', 'UNKNOWN'].includes(value)) || issues.length) {
    return { status: 'PARTIAL', issues, fetchedAt: '' }
  }
  return { status: 'READY', issues, fetchedAt: '' }
}
