import request from '@/utils/request'
import storage from 'store'
import { ACCESS_TOKEN } from '@/store/mutation-types'
import { hasAccessToken } from '@/utils/guestAccess'
import { PUBLIC_MARKET_ENDPOINTS } from './publicMarketEndpoints'

const AUTHENTICATED_SMART_INSIGHTS_ENDPOINTS = Object.freeze({
  overview: '/api/smart-insights/overview',
  dates: '/api/smart-insights/dates'
})

function smartInsightsEndpoint (publicEndpoint, authenticatedEndpoint) {
  return hasAccessToken(storage.get(ACCESS_TOKEN)) ? authenticatedEndpoint : publicEndpoint
}

export function getSmartInsightsOverview (params = {}) {
  return request({
    url: smartInsightsEndpoint(PUBLIC_MARKET_ENDPOINTS.smartInsightsOverview, AUTHENTICATED_SMART_INSIGHTS_ENDPOINTS.overview),
    method: 'get',
    params
  })
}

export function getSmartInsightsDates (params = {}) {
  return request({
    url: smartInsightsEndpoint(PUBLIC_MARKET_ENDPOINTS.smartInsightsDates, AUTHENTICATED_SMART_INSIGHTS_ENDPOINTS.dates),
    method: 'get',
    params
  })
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

export function getPublicResearchReport (assetKey, reportKind) {
  return request({
    url: `/api/smart-insights/public/reports/${encodeURIComponent(String(assetKey || ''))}/${encodeURIComponent(String(reportKind || ''))}`,
    method: 'get',
    // Public research is generated once in vi-VN. Keep it readable for
    // guests even when the surrounding UI is currently en-US.
    params: { lang: 'vi-VN' }
  })
}

export function getPublicResearchReportPdf (assetKey, revision) {
  return request({
    url: `/api/smart-insights/public/reports/${encodeURIComponent(String(assetKey || ''))}/deep.pdf`,
    method: 'get',
    params: { lang: 'vi-VN', r: revision },
    responseType: 'blob',
    timeout: 120000
  })
}

export function getPublicResearchReportSummaryPdf (assetKey, revision) {
  return request({
    url: `/api/smart-insights/public/reports/${encodeURIComponent(String(assetKey || ''))}/deep-summary.pdf`,
    method: 'get',
    params: { lang: 'vi-VN', r: revision },
    responseType: 'blob',
    timeout: 120000
  })
}

export function getSharedResearchReports () {
  return request({ url: '/api/smart-insights/research/reports', method: 'get' })
}

export function requestSharedResearchReport (assetKey, reportKind) {
  return request({
    url: `/api/smart-insights/research/reports/${encodeURIComponent(String(assetKey || ''))}/${encodeURIComponent(String(reportKind || ''))}`,
    method: 'post'
  })
}

export function getSharedResearchReportPdf (assetKey, revision, variant = 'full') {
  const suffix = variant === 'summary' ? 'deep-summary.pdf' : 'deep.pdf'
  return request({
    url: `/api/smart-insights/research/reports/${encodeURIComponent(String(assetKey || ''))}/${suffix}`,
    method: 'get',
    params: { lang: 'vi-VN', r: revision },
    responseType: 'blob',
    timeout: 120000
  })
}
