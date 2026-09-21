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
  assert.match(component, /hoseOnly/)
})
