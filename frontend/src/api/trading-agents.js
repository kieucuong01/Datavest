import request from '@/utils/request'

export function createTradingAgentsRun (payload) {
  return request({ url: '/api/trading-agents/runs', method: 'post', data: payload, timeout: 30000 })
}

export function getTradingAgentsRun (runId, timeout = 30000) {
  return request({ url: `/api/trading-agents/runs/${encodeURIComponent(runId)}`, method: 'get', timeout })
}

export function getTradingAgentsRuns (params, timeout = 8000) {
  return request({ url: '/api/trading-agents/runs', method: 'get', params, timeout })
}

export function cancelTradingAgentsRun (runId) {
  return request({ url: `/api/trading-agents/runs/${encodeURIComponent(runId)}/cancel`, method: 'post', timeout: 30000 })
}

export function resumeTradingAgentsRun (runId) {
  return request({ url: `/api/trading-agents/runs/${encodeURIComponent(runId)}/resume`, method: 'post', timeout: 30000 })
}

export function clearTradingAgentsCheckpoint (runId) {
  return request({ url: `/api/trading-agents/runs/${encodeURIComponent(runId)}/clear-checkpoint`, method: 'post', timeout: 30000 })
}

export function getTradingAgentsArtifact (runId, artifactName) {
  return request({
    url: `/api/trading-agents/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactName)}`,
    method: 'get',
    responseType: 'text',
    timeout: 30000
  })
}

export function getTradingAgentsReportPdf (runId, revision) {
  return request({
    url: `/api/trading-agents/runs/${encodeURIComponent(runId)}/report.pdf`,
    method: 'get',
    params: { r: revision },
    responseType: 'blob',
    timeout: 120000
  })
}

export function getTradingAgentsSummaryPdf (runId, revision) {
  return request({
    url: `/api/trading-agents/runs/${encodeURIComponent(runId)}/summary.pdf`,
    method: 'get',
    params: { r: revision },
    responseType: 'blob',
    timeout: 120000
  })
}
