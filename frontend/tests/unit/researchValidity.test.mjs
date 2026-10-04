import assert from 'node:assert/strict'
import test from 'node:test'
import { reportValidity } from '../../src/views/smart-insights/reportValidity.js'

test('old and undated reports cannot appear as current advice', () => {
  const now = Date.parse('2026-10-04T17:00:00Z')
  assert.equal(reportValidity({ effectiveDate: '2026-09-30', generatedAt: '2026-10-05' }, now).actionable, false)
  assert.equal(reportValidity({ effectiveDate: '2026-10-05' }, now).actionable, true)
  assert.equal(reportValidity({}, now).actionable, false)
  assert.equal(reportValidity({ effectiveDate: '2026-10-12' }, now).actionable, false)
})
