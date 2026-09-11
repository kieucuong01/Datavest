import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { normalizeQuickAnalysisReport } from '../../src/views/smart-insights/quickAnalysisHistory.js'

const read = relative => readFileSync(new URL(`../../${relative}`, import.meta.url), 'utf8')

test('normalizes an AI Assistant history item to the same safe report shape as Smart Insights', () => {
  const report = normalizeQuickAnalysisReport({
    id: 12,
    market: 'Crypto',
    symbol: 'BTC/USDT',
    created_at: '2026-09-11T02:00:00Z',
    decision: 'HOLD',
    confidence: 64,
    summary: 'Đang chờ xác nhận.',
    full_result: {
      model: 'deepseek-chat',
      timeframe: '1D',
      detailed_analysis: { technical: 'MACD đi ngang.' },
      input_data: { captured_at: '2026-09-11T01:55:00Z', checksum: 'abc' }
    }
  })

  assert.deepEqual(report, {
    id: 12,
    market: 'Crypto',
    symbol: 'BTC/USDT',
    createdAt: '2026-09-11T02:00:00Z',
    updatedAt: null,
    status: 'completed',
    decision: 'HOLD',
    confidence: 64,
    summary: 'Đang chờ xác nhận.',
    reasons: [],
    scores: {},
    model: 'deepseek-chat',
    language: null,
    timeframe: '1D',
    detailedAnalysis: { technical: 'MACD đi ngang.' },
    tradingPlan: {},
    risks: [],
    marketData: {},
    inputData: {
      capturedAt: '2026-09-11T01:55:00Z',
      priceSource: null,
      timeframe: null,
      klineAt: null,
      checksum: 'abc',
      components: []
    },
    indicators: {},
    cryptoFactors: {},
    cryptoFactorScore: null,
    cryptoFactorBreakdown: [],
    cryptoFactorSummary: '',
    objectiveScore: {},
    scoreBasedDecision: null,
    consensus: {},
    trendOutlook: {},
    trendOutlookSummary: '',
    analysisTimeMs: null,
    llmTimeMs: null,
    dataCollectionTimeMs: null
  })
})

test('Smart Insights exposes history in both analysis modes and removes the top date filter', () => {
  const page = read('src/views/smart-insights/index.vue')
  const deepPanel = read('src/components/TradingAgents/DeepAnalysisPanel.vue')
  const api = read('src/api/fast-analysis.js')

  assert.doesNotMatch(page, /<section class="analysis-controls"/u)
  assert.match(api, /getAnalysisHistory/u)
  assert.match(page, /quickAnalysisHistory/u)
  assert.match(page, /loadQuickAnalysisHistory/u)
  assert.match(page, /selectQuickAnalysisHistory/u)
  assert.match(page, /quick-analysis-history/u)
  assert.match(deepPanel, /v-if="run && isSupported && historyReports.length"/u)
  assert.match(deepPanel, /created \(\) \{[\s\S]*this\.loadReportHistory\(\)/u)
  assert.match(deepPanel, /this\.loadReportHistory\(\)/u)
})
