import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../..', import.meta.url))
const read = (relative) => readFileSync(`${root}/${relative}`, 'utf8')

test('deep analysis loads the report library and requires an explicit user action to start a run', () => {
  const panel = read('src/components/TradingAgents/DeepAnalysisPanel.vue')
  const api = read('src/api/trading-agents.js')

  assert.match(panel, /loadReportHistory/u)
  assert.doesNotMatch(panel, /loadLatestRun\(\{ autoStart: true \}\)/u)
  assert.match(panel, /HISTORY_TIMEOUT_MS\s*=\s*8000/u)
  assert.match(panel, /historyError/u)
  assert.match(panel, /completed_stage_ids/u)
  assert.match(panel, /currentStageLabel/u)
  assert.match(panel, /progressElapsedLabel/u)
  assert.match(panel, /stageDetails/u)
  assert.match(api, /timeout\s*=\s*8000/u)
})

test('deep analysis renders verified stage progress instead of deriving a fixed percentage from event count', () => {
  const panel = read('src/components/TradingAgents/DeepAnalysisPanel.vue')

  assert.match(panel, /progressSnapshot\.percent/u)
  assert.match(panel, /progressSnapshot\.current_stage_id/u)
  assert.doesNotMatch(panel, /12 \+ count \* 7/u)
})
