import assert from 'node:assert/strict'
import test from 'node:test'
import { buildResearchDecisionBrief, comparablePreviousReport } from '../../src/utils/researchDecisionBrief.js'

const report = (day, rating = 'HOLD') => ({ assetKey: 'vnstock:FPT', reportKind: 'deep', locale: 'vi-VN', effectiveDate: day, body: `
## I. Analyst Team Reports
### Market Analyst
**Rating**: BUY
## V. Portfolio Manager Decision
### Portfolio Manager
**Rating**: ${rating}
**Executive Summary**: Chờ BCTC quý tới.
**Time Horizon**: 3 tháng
### Supporting Evidence
- Doanh thu tăng 20%, FY2025 [BCTC](https://example.com/filing).
### Counter Evidence
- Dòng tiền hoạt động chưa theo kịp lợi nhuận.
### Key Risks
- Định giá phụ thuộc kỳ vọng tăng trưởng.
### Invalidation Conditions
- Nếu doanh thu quý tới giảm so với cùng kỳ, đánh giá lại luận điểm.
### Next Watch
- Kiểm tra BCTC quý tới và chất lượng dòng tiền.
` })

test('uses the final manager decision and exact evidence, risk and invalidation sections', () => {
  const brief = buildResearchDecisionBrief(report('2026-10-05'), report('2026-09-28', 'BUY'))
  assert.equal(brief.rating, 'HOLD')
  assert.equal(brief.timeHorizon, '3 tháng')
  assert.equal(brief.supporting[0].sourceUrl, 'https://example.com/filing')
  assert.match(brief.counter[0].text, /Dòng tiền/u)
  assert.match(brief.invalidation[0].text, /doanh thu quý tới giảm/u)
  assert.equal(brief.comparison.previousDate, '2026-09-28')
  assert.deepEqual(brief.comparison.rating, { before: 'BUY', after: 'HOLD', changed: true })
})

test('does not invent a missing risk, invalidation, source URL or prior period', () => {
  const brief = buildResearchDecisionBrief({ ...report('2026-10-05'), body: '## V. Portfolio Manager Decision\n**Rating**: HOLD' })
  assert.deepEqual(brief.risks, [])
  assert.deepEqual(brief.invalidation, [])
  assert.deepEqual(brief.supporting, [])
  assert.equal(brief.comparison, null)
})

test('missing prior fields are not interpreted as a new rating or a newly emerged risk', () => {
  const old = { ...report('2026-09-28'), body: '## V. Portfolio Manager Decision\n**Executive Summary**: Chưa đủ dữ liệu.' }
  const brief = buildResearchDecisionBrief(report('2026-10-05'), old)
  assert.equal(brief.comparison.rating.changed, null)
  assert.equal(brief.comparison.riskComparisonAvailable, false)
  assert.deepEqual(brief.comparison.addedRisks, [])
})

test('rejects future, same-period, different-asset and different-language comparisons', () => {
  const current = report('2026-10-05')
  for (const previous of [report('2026-10-12'), report('2026-10-05'), { ...report('2026-09-28'), assetKey: 'vnstock:HPG' }, { ...report('2026-09-28'), locale: 'en-US' }]) {
    assert.equal(comparablePreviousReport(current, previous), false)
    assert.equal(buildResearchDecisionBrief(current, previous).comparison, null)
  }
})

test('keeps unsafe source links inert and never uses analyst risk prose as final-manager conditions', () => {
  const brief = buildResearchDecisionBrief({ ...report('2026-10-05'), body: '## IV. Risk Management Team Decision\n### Invalidation Conditions\n- Analyst guess\n## V. Portfolio Manager Decision\n**Supporting Evidence**: [source](javascript:alert(1))' })
  assert.deepEqual(brief.invalidation, [])
  assert.equal(brief.supporting[0].sourceUrl, '')
})
