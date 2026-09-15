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

test('extracts a single-line executive summary used by production TradingAgents reports', () => {
  const summary = extractPortfolioManagerDecisionSummary(`
# Trading Analysis Report: BTC-USD
Generated: 2026-09-14 08:06:19
## V. Portfolio Manager Decision
### Portfolio Manager
**Rating**: Hold
**Executive Summary**: Giữ nguyên vị thế lõi BTC-USD, không tăng và không xả trước FOMC. Không mua đuổi quanh 77k. Khung thời gian: 1–4 tuần, đánh giá lại sau phản ứng của Fed.
`)

  assert.deepEqual(summary, {
    rating: 'Hold',
    timeHorizon: '1–4 tuần, đánh giá lại sau phản ứng của Fed',
    actions: [
      'Giữ nguyên vị thế lõi BTC-USD, không tăng và không xả trước FOMC.',
      'Không mua đuổi quanh 77k.',
      'Khung thời gian: 1–4 tuần, đánh giá lại sau phản ứng của Fed.'
    ]
  })
})

test('extracts the full wrapped production executive summary without PDF footer noise', () => {
  const summary = extractPortfolioManagerDecisionSummary(`
V. Portfolio Manager Decision
Portfolio Manager
Rating: Hold
Executive Summary: Giữ nguyên vị thế lõi BTC-USD ở mức HOLD, KHÔNG mua đuổi tại 78.386,20
vì giá đang nằm dưới VWMA (78.910), dưới EMA10 và dưới đường giữa Bollinger (78.702). Chấp nhận
một động thái hạ beta có giới hạn — cắt tỉa 5–10% vị thế trước FOMC 16/09 — và giảm sizing tổng
25–30% so với điều kiện yên ắng, không dùng đòn bẩy, giữ tiền mặt dự phòng cho cả hai kịch bản.
Stop cứng dưới vùng hội tụ 76.248–76.462 với một khoảng đệm thực sự; nếu thủng 76.248 kèm khối
lượng, hạ về mức phòng thủ và chuyển kịch bản sang 70.000–72.000. Chỉ thêm vị thế khi có đóng
cửa ngày TRÊN 78.910 KÈM khối lượng >40 tỷ, hoặc DCA từng phần tại 76.400–76.500 chỉ khi xuất
hiện nến đảo chiều xác nhận.
Không phải tư vấn đầu tư hoặc lệnh giao dịch. DataVest - TradingAgents - 45
Investment Thesis: Cấu trúc trung–dài hạn còn tăng.
Time Horizon: 2–6 tuần
`)

  assert.equal(summary.rating, 'Hold')
  assert.equal(summary.timeHorizon, '2–6 tuần')
  assert.equal(summary.actions.length, 4)
  assert.match(summary.actions[0], /Giữ nguyên vị thế lõi BTC-USD/u)
  assert.match(summary.actions[1], /cắt tỉa 5–10%/u)
  assert.match(summary.actions[2], /Stop cứng/u)
  assert.match(summary.actions[3], /Chỉ thêm vị thế/u)
  assert.ok(summary.actions.every((action) => !action.includes('DataVest - TradingAgents')))
})
