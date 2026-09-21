import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  hosePriceLabel,
  hoseLatencyLabel,
  hoseScoreLabel,
  hoseCoverageRows,
  hasScore
} from '../../src/utils/hosePresentation.js'

test('HOSE prices and missing scores never look like USD or neutral 50', () => {
  assert.equal(hosePriceLabel(120000), '120.000 VND')
  assert.equal(hosePriceLabel(null), '--')
  assert.equal(hoseScoreLabel(null, 'vi-VN'), 'Không đủ dữ liệu')
  assert.equal(hoseScoreLabel(0, 'vi-VN'), '0')
  assert.equal(hasScore(null), false)
  assert.equal(hasScore(0), true)
})

test('unknown latency stays unknown and coverage exposes gaps', () => {
  assert.equal(hoseLatencyLabel({ price: { latencyClass: 'unknown' } }, 'vi-VN'), 'Chưa xác định')
  assert.equal(hoseLatencyLabel({ price: { latencyClass: 'eod' } }, 'en-US'), 'EOD')
  assert.deepEqual(hoseCoverageRows({ fundamentals: { status: 'missing', reason: 'NO_STATEMENTS' } }), [
    { key: 'fundamentals', status: 'missing', reason: 'NO_STATEMENTS' }
  ])
})

test('Copilot filters HOSE server-side and does not invent a VN fallback symbol', () => {
  const component = readFileSync(new URL('../../src/views/ai-analysis/components/CopilotWorkbench.vue', import.meta.url), 'utf8')
  assert.match(component, /exchange: 'HOSE'/)
  assert.match(component, /manualAddWatchFallback \(market, keyword\) \{[\s\S]*?if \(market === 'VNStock'\) return \[\]/)
  assert.match(component, /hoseProvenanceRows/)
  assert.match(component, /hose_provenance/)
  assert.match(component, /HOSE · VND/)
  assert.match(component, /hoseOnly/)
})

test('Copilot never uses handwritten Vietnamese company aliases or picks the first HOSE hit', () => {
  const component = readFileSync(new URL('../../src/views/ai-analysis/components/CopilotWorkbench.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(component, /keys: \['fpt'\], market: 'VNStock'/)
  assert.doesNotMatch(component, /keys: \['vietcombank', 'vcb'\], market: 'VNStock'/)
  assert.match(component, /filter\(item => item\.market !== 'VNStock'\)/)
})

test('portfolio forms search the active HOSE catalog instead of fabricating a ticker', () => {
  const optimizer = readFileSync(new URL('../../src/views/portfolio-optimizer/index.vue', import.meta.url), 'utf8')
  const mockPortfolio = readFileSync(new URL('../../src/views/mock-portfolio/index.vue', import.meta.url), 'utf8')
  for (const component of [optimizer, mockPortfolio]) {
    assert.match(component, /searchSymbols\(\{ market: 'VNStock', exchange: 'HOSE'/)
    assert.match(component, /a-auto-complete/)
  }
  assert.doesNotMatch(mockPortfolio, /this\.form\.market === 'VNStock'\) this\.form\.symbol = 'FPT'/)
})
