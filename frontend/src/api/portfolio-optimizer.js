import request from '@/utils/request'

export function createOptimizerRun (data) {
  return request({ url: '/api/portfolio/optimizer/runs', method: 'post', data, timeout: 120000 })
}

export function getOptimizerRun (runId) {
  return request({ url: `/api/portfolio/optimizer/runs/${runId}`, method: 'get' })
}

export function previewOptimizerRun (runId, portfolioValue) {
  return request({
    url: `/api/portfolio/optimizer/runs/${runId}/preview`,
    method: 'post',
    data: { portfolioValue }
  })
}

export function applyOptimizerRun (runId, planId, idempotencyKey) {
  return request({
    url: `/api/portfolio/optimizer/runs/${runId}/apply`,
    method: 'post',
    data: { planId, idempotencyKey }
  })
}
