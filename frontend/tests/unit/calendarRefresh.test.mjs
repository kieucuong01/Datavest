import test from 'node:test'
import assert from 'node:assert/strict'
import { calendarCacheFresh, calendarMissingValue } from '../../src/views/smart-insights/calendarRefresh.js'
test('calendar cache expires after five minutes', () => {
  assert.equal(calendarCacheFresh({ loadedAt: 1000 }, 300999), true)
  assert.equal(calendarCacheFresh({ loadedAt: 1000 }, 301000), false)
  assert.equal(calendarCacheFresh({}, 1000), false)
})
test('missing actual distinguishes a future VN event from unavailable released data', () => {
  const now = Date.parse('2026-09-11T12:00:00Z')
  assert.equal(calendarMissingValue({date:'2026-09-11',time:'21:00'}, 'actual', true, now), 'Chưa công bố')
  assert.equal(calendarMissingValue({date:'2026-09-11',time:'18:00'}, 'actual', true, now), 'Chưa có số liệu')
  assert.equal(calendarMissingValue({}, 'forecast', false, now), 'Not provided')
})
