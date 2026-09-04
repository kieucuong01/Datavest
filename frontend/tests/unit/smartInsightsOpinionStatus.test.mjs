import assert from 'node:assert/strict'
import test from 'node:test'

import { buildOpinionPresentation } from '../../src/views/smart-insights/opinionStatus.js'

test('presents a fresh report with its scheduled monitor and input timestamp', () => {
  const presentation = buildOpinionPresentation({
    analysisStatus: 'AVAILABLE',
    dataFreshness: 'FRESH',
    monitor: { state: 'SCHEDULED', nextRunAt: '2026-09-04T10:00:00+00:00' },
    report: { inputData: { capturedAt: '2026-09-04T09:00:00+00:00' } }
  })

  assert.deepEqual(presentation, {
    status: 'AVAILABLE',
    freshness: 'FRESH',
    monitorState: 'SCHEDULED',
    capturedAt: '2026-09-04T09:00:00+00:00',
    nextRunAt: '2026-09-04T10:00:00+00:00',
    needsAssistant: false
  })
})

test('routes a paused or missing report back to AI Assistant instead of a blank modal', () => {
  const presentation = buildOpinionPresentation({
    analysisStatus: 'PAUSED',
    monitor: { state: 'PAUSED' },
    report: null
  })

  assert.equal(presentation.status, 'PAUSED')
  assert.equal(presentation.needsAssistant, true)
})
