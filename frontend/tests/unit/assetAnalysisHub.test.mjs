import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = relative => readFileSync(new URL(`../../${relative}`, import.meta.url), 'utf8')

test('Smart Insights presents quick and deep analysis in one asset-analysis hub', () => {
  const page = read('src/views/smart-insights/index.vue')
  const opinions = read('src/views/smart-insights/components/AssetOpinionsSection.vue')
  const tradingAgents = read('src/components/TradingAgents/DeepAnalysisPanel.vue')

  assert.match(page, /analysis-mode-switcher/u)
  assert.match(page, /analysisMode/u)
  assert.match(page, /@click="analysisMode = 'quick'"/u)
  assert.match(page, /@click="analysisMode = 'deep'"/u)
  assert.match(page, /:embedded="true"/u)
  assert.match(page, /openAssetAnalysis \(row, mode = 'quick'\)/u)
  assert.match(page, /this\.analysisMode = mode === 'deep' \? 'deep' : 'quick'/u)
  assert.match(opinions, /quick-analysis-action/u)
  assert.match(opinions, /deep-analysis-action/u)
  assert.match(tradingAgents, /embedded: \{ type: Boolean, default: false \}/u)
  assert.match(tradingAgents, /get-container="embedded \? false : undefined"/u)
})
