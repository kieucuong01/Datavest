import assert from 'node:assert/strict'
import test from 'node:test'

import { PUBLIC_MARKET_ENDPOINTS } from '../../src/api/publicMarketEndpoints.js'

test('guest market pages only use explicitly public read endpoints', () => {
  assert.deepEqual(PUBLIC_MARKET_ENDPOINTS, {
    smartInsightsOverview: '/api/smart-insights/public/overview',
    smartInsightsDates: '/api/smart-insights/public/dates',
    smartInsightsEvidence: '/api/smart-insights/public/evidence',
    smartInsightsDataHealth: '/api/smart-insights/public/data-health',
    smartInsightsLiveAssets: '/api/smart-insights/public/live-assets',
    smartInsightsCryptoPulse: '/api/smart-insights/public/crypto-market-pulse',
    economicCalendar: '/api/global-market/public/calendar'
  })
})
