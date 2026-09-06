import assert from 'node:assert/strict'
import test from 'node:test'

import {
  localizeTradingAgentsHeading,
  parseTradingAgentsReport
} from '../../src/utils/tradingAgentsReport.js'

test('parses the native markdown report into readable text blocks', () => {
  const blocks = parseTradingAgentsReport('# Báo cáo\n\nGenerated: 2026-09-05 10:00:00\n\n## Thị trường\n\n**Xu hướng:** tích cực\n\n- Hỗ trợ: 100\n- Rủi ro: 120')

  assert.deepEqual(blocks, [
    { type: 'heading', level: 1, text: 'Báo cáo' },
    { type: 'heading', level: 2, text: 'Thị trường' },
    { type: 'paragraph', text: 'Xu hướng: tích cực' },
    { type: 'list', items: ['Hỗ trợ: 100', 'Rủi ro: 120'] }
  ])
})

test('localizes fixed native report headings when the UI is Vietnamese', () => {
  assert.equal(
    localizeTradingAgentsHeading('I. Analyst Team Reports', 'vi-VN'),
    'I. Báo cáo nhóm phân tích'
  )
  assert.equal(
    localizeTradingAgentsHeading('V. Portfolio Manager Decision', 'vi-VN'),
    'V. Quyết định của quản lý danh mục'
  )
  assert.equal(
    localizeTradingAgentsHeading('Market Analyst', 'en-US'),
    'Market Analyst'
  )
})
