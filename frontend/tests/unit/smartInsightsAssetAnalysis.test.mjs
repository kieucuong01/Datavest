import assert from 'node:assert/strict'
import test from 'node:test'

import { buildAssetAnalysisDetails, canShowTradingPlan } from '../../src/views/smart-insights/analysisReport.js'

test('normalizes the full AI Assistant report for the Smart Insights modal', () => {
  const report = {
    detailedAnalysis: { technical: 'MACD suy yếu.' },
    tradingPlan: { entry_price: 100, stop_loss: 95, take_profit: 110 },
    risks: ['Biến động cao'],
    marketData: { current_price: 101 },
    indicators: { rsi: { value: 63.49 } },
    cryptoFactors: { funding_rate: 0.01 },
    cryptoFactorBreakdown: [{ factor: 'funding_oi', score: -18 }],
    consensus: { consensus_decision: 'SELL' },
    trendOutlook: { next_24h: { trend: 'SELL', score: -20 } },
    trendOutlookSummary: 'Ngắn hạn nghiêng về giảm.'
  }

  const details = buildAssetAnalysisDetails(report)

  assert.equal(details.detailedAnalysis.technical, 'MACD suy yếu.')
  assert.equal(details.tradingPlan.entry_price, 100)
  assert.deepEqual(details.risks, ['Biến động cao'])
  assert.equal(details.marketData.current_price, 101)
  assert.equal(details.indicators.rsi.value, 63.49)
  assert.equal(details.cryptoFactors.funding_rate, 0.01)
  assert.equal(details.cryptoFactorBreakdown[0].factor, 'funding_oi')
  assert.equal(details.consensus.consensus_decision, 'SELL')
  assert.equal(details.trendOutlook.next_24h.score, -20)
  assert.equal(details.trendOutlookSummary, 'Ngắn hạn nghiêng về giảm.')
})

test('returns safe empty defaults when the report has no detail payload', () => {
  const details = buildAssetAnalysisDetails(null)

  assert.deepEqual(details.detailedAnalysis, {})
  assert.deepEqual(details.risks, [])
  assert.deepEqual(details.indicators, {})
  assert.deepEqual(details.cryptoFactorBreakdown, [])
  assert.deepEqual(details.trendOutlook, {})
})

test('only exposes a reference plan for a sufficiently confident directional report', () => {
  const plan = { entry_price: 100, stop_loss: 95, take_profit: 110 }

  assert.equal(canShowTradingPlan({ decision: 'BUY', confidence: 60, tradingPlan: plan }), true)
  assert.equal(canShowTradingPlan({ decision: 'HOLD', confidence: 80, tradingPlan: plan }), false)
  assert.equal(canShowTradingPlan({ decision: 'SELL', confidence: 59, tradingPlan: plan }), false)
})
