import assert from 'node:assert/strict'
import test from 'node:test'

import { formatVietnamDate, formatVietnamDateTime, VIETNAM_TIME_ZONE } from '../../src/utils/vietnamTime.js'

test('formats an UTC report instant in Vietnam time regardless of browser timezone', () => {
  assert.equal(VIETNAM_TIME_ZONE, 'Asia/Ho_Chi_Minh')
  assert.equal(
    formatVietnamDateTime('2026-09-04T20:30:00Z', { locale: 'en-GB' }),
    '05/09/2026, 03:30'
  )
})

test('keeps a Vietnam calendar day stable for UTC timestamps near midnight', () => {
  assert.equal(
    formatVietnamDate('2026-09-04T20:30:00Z', { locale: 'vi-VN' }),
    '05/09/2026'
  )
})
