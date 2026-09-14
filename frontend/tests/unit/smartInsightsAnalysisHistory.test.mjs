import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = relative => readFileSync(new URL(`../../${relative}`, import.meta.url), 'utf8')

test('Smart Insights opens TradingAgents research as its only analysis flow', () => {
  const page = read('src/views/smart-insights/index.vue')

  assert.doesNotMatch(page, /fast-analysis/u)
  assert.match(page, /analysisMode: 'deep'/u)
  assert.match(page, /await this\.loadPublicDeepReport\(row\)/u)
  assert.doesNotMatch(page, /loadQuickAnalysisHistory\(row\)/u)
})
