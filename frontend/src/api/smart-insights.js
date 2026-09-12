import request from '@/utils/request'
import { PUBLIC_MARKET_ENDPOINTS } from './publicMarketEndpoints'

export function getSmartInsightsOverview (params = {}) {
  return request({ url: PUBLIC_MARKET_ENDPOINTS.smartInsightsOverview, method: 'get', params })
}

export function getSmartInsightsDates (params = {}) {
  return request({ url: PUBLIC_MARKET_ENDPOINTS.smartInsightsDates, method: 'get', params })
}

export function getSmartInsightsEvidence (evidenceId) {
  return request({ url: `${PUBLIC_MARKET_ENDPOINTS.smartInsightsEvidence}/${evidenceId}`, method: 'get' })
}

export function getSmartInsightsDataHealth () {
  return request({ url: PUBLIC_MARKET_ENDPOINTS.smartInsightsDataHealth, method: 'get' })
}

export function getSmartInsightsLiveAssets () {
  return request({ url: PUBLIC_MARKET_ENDPOINTS.smartInsightsLiveAssets, method: 'get' })
}

export function getSmartInsightsCryptoPulse (params = {}) {
  return request({ url: PUBLIC_MARKET_ENDPOINTS.smartInsightsCryptoPulse, method: 'get', params })
}
