import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = relative => readFileSync(new URL(`../../${relative}`, import.meta.url), 'utf8')

test('Smart Insights presents TradingAgents research without AI Assistant quick analysis', () => {
  const page = read('src/views/smart-insights/index.vue')
  const opinions = read('src/views/smart-insights/components/AssetOpinionsSection.vue')
  const tradingAgents = read('src/components/TradingAgents/DeepAnalysisPanel.vue')

  assert.match(page, /analysisMode: 'deep'/u)
  assert.doesNotMatch(page, /@open-analysis=/u)
  assert.doesNotMatch(page, /@create-analysis=/u)
  assert.match(page, /<report-pdf-reader/u)
  assert.match(page, /openAssetAnalysis \(row\)/u)
  assert.doesNotMatch(opinions, /quick-analysis-action/u)
  assert.match(opinions, /deep-analysis-action/u)
  assert.match(opinions, /create-deep-analysis/u)
  assert.match(tradingAgents, /embedded: \{ type: Boolean, default: false \}/u)
})
