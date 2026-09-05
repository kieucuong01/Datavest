import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../..', import.meta.url))
const read = (relative) => readFileSync(new URL(`../../${relative}`, import.meta.url), 'utf8')

test('deep analysis is a shared, owner-scoped TradingAgents panel', () => {
  const panelPath = new URL('../../src/components/TradingAgents/DeepAnalysisPanel.vue', import.meta.url)
  assert.ok(existsSync(panelPath), 'the reusable deep analysis panel must exist')

  const api = read('src/api/trading-agents.js')
  const panel = read('src/components/TradingAgents/DeepAnalysisPanel.vue')
  const locale = read('src/locales/trading-agents.js')
  const opinions = read('src/views/smart-insights/components/AssetOpinionsSection.vue')
  const smartInsights = read('src/views/smart-insights/index.vue')
  const copilot = read('src/views/ai-analysis/components/CopilotWorkbench.vue')

  assert.match(api, /\/api\/trading-agents\/runs/u)
  assert.match(api, /cancelTradingAgentsRun/u)
  assert.match(panel, /v-text="reportContent"/u)
  assert.doesNotMatch(panel, /v-html=/u)
  assert.match(panel, /getTradingAgentsRun/u)
  assert.match(panel, /setInterval/u)
  assert.match(panel, /FULL_ANALYSTS = \['market', 'social', 'news', 'fundamentals'\]/u)
  assert.match(panel, /analysisDate/u)
  assert.match(panel, /@media \(max-width: 640px\)/u)
  assert.match(opinions, /open-deep-analysis/u)
  assert.match(smartInsights, /DeepAnalysisPanel/u)
  assert.match(copilot, /openDeepAnalysis/u)
  assert.match(copilot, /deepAnalysisVisible/u)
  assert.match(copilot, /tradingAgents\.trigger/u)
  assert.match(locale, /Phân tích chuyên sâu mã/u)
  assert.ok(root.includes('frontend'), 'the contract remains scoped to the Vue frontend')
})
