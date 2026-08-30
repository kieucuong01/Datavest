import request from '@/utils/request'

export function getSmartInsightsOverview (params = {}) {
  return request({ url: '/api/smart-insights/overview', method: 'get', params })
}

export function getSmartInsightsDates (params = {}) {
  return request({ url: '/api/smart-insights/dates', method: 'get', params })
}

export function getSmartInsightsEvidence (evidenceId) {
  return request({ url: `/api/smart-insights/evidence/${evidenceId}`, method: 'get' })
}

export function getSmartInsightsDataHealth () {
  return request({ url: '/api/smart-insights/data-health', method: 'get' })
}

export function getSmartInsightsLiveAssets () {
  return request({ url: '/api/smart-insights/live-assets', method: 'get' })
}

export function getSmartInsightsCryptoPulse (params = {}) {
  return request({ url: '/api/smart-insights/crypto-market-pulse', method: 'get', params })
}
