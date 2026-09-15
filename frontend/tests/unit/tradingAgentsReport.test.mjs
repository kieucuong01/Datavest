import assert from 'node:assert/strict'
import test from 'node:test'

import {
  extractPortfolioManagerDecisionSummary,
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

test('extracts the portfolio manager decision summary for asset opinion cards', () => {
  const summary = extractPortfolioManagerDecisionSummary(`
## V. Portfolio Manager Decision
Portfolio Manager Rating: **HOLD**
Time Horizon: 1-4 weeks, reassess after the FOMC meeting.

### Executive Summary
- **Core strategy:** Keep the BTC core position; do not chase price before FOMC.
- **Capital management:** Reduce total sizing by 25-30% and avoid leverage.
- **Stop-loss discipline:** Use a hard stop below 76,248 with a volatility buffer.
`)

  assert.deepEqual(summary, {
    rating: 'HOLD',
    timeHorizon: '1-4 weeks, reassess after the FOMC meeting.',
    actions: [
      'Core strategy: Keep the BTC core position; do not chase price before FOMC.',
      'Capital management: Reduce total sizing by 25-30% and avoid leverage.',
      'Stop-loss discipline: Use a hard stop below 76,248 with a volatility buffer.'
    ]
  })
})
