import assert from 'node:assert/strict'
import test from 'node:test'

import {
  groupTradingAgentsReportSections,
  parseTradingAgentsReport
} from '../../src/utils/tradingAgentsReport.js'

test('native analyst headings stay under their team even when AI emits H1', () => {
  const report = groupTradingAgentsReportSections(parseTradingAgentsReport('# Trading Analysis Report: BTC\n## I. Analyst Team Reports\n### Market Analyst\n# Market review\n## Price\n### Risk\nDeep content\n### Sentiment Analyst\n# Social review\nSocial content\n## II. Research Team Decision\nDecision'))
  assert.equal(report.sections.length, 2)
  assert.equal(report.sections[0].subsections.length, 2)
  assert.equal(report.sections[0].subsections[0].subsections[0].subsections[0].subsections[0].blocks[0].text, 'Deep content')
})

test('fenced code and lone pipe text are not discarded or treated as report headings', () => {
  const blocks = parseTradingAgentsReport('```text\n# not a heading\n```\n\n| source pending')
  assert.equal(blocks[0].type, 'code')
  assert.equal(blocks[0].text, '# not a heading')
  assert.equal(blocks[1].text, '| source pending')
})

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
