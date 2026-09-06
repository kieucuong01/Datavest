import assert from 'node:assert/strict'
import test from 'node:test'

import {
  groupTradingAgentsReportSections,
  parseTradingAgentsReport
} from '../../src/utils/tradingAgentsReport.js'

test('groups the native report into readable top-level sections and tables', () => {
  const blocks = parseTradingAgentsReport('# Báo cáo BTC\n\n## Thị trường\n\n### Xu hướng\n\nTăng nhẹ.\n\n| Chỉ báo | Giá trị |\n| --- | --- |\n| RSI | 62 |\n\n## Rủi ro\n\n- Thanh khoản thấp')
  const report = groupTradingAgentsReportSections(blocks)

  assert.equal(report.title, 'Báo cáo BTC')
  assert.deepEqual(report.sections.map(section => section.title), ['Thị trường', 'Rủi ro'])
  assert.deepEqual(report.sections[0].subsections.map(section => section.title), ['Xu hướng'])
  assert.equal(report.sections[0].subsections[0].blocks[0].text, 'Tăng nhẹ.')
  assert.deepEqual(report.sections[0].subsections[0].blocks[1], {
    type: 'table',
    headers: ['Chỉ báo', 'Giá trị'],
    rows: [['RSI', '62']]
  })
  assert.deepEqual(report.sections[1].blocks[0], { type: 'list', items: ['Thanh khoản thấp'] })
})
