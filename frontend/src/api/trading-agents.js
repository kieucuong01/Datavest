import request from '@/utils/request'

export function createTradingAgentsRun (payload) {
  return request({ url: '/api/trading-agents/runs', method: 'post', data: payload, timeout: 30000 })
}

export function getTradingAgentsRun (runId) {
  return request({ url: `/api/trading-agents/runs/${encodeURIComponent(runId)}`, method: 'get' })
}

export function getTradingAgentsRuns (params) {
  return request({ url: '/api/trading-agents/runs', method: 'get', params })
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
