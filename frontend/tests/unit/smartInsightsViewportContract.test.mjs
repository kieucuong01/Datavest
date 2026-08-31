import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const smartInsightsSource = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
const mockPortfolioSource = fs.readFileSync(new URL('../../src/views/mock-portfolio/index.vue', import.meta.url), 'utf8')

function styleRule (source, selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/gu, '\\$&')
  const match = source.match(new RegExp(`${escapedSelector} \\{[^}]*\\}`, 'u'))
  assert.ok(match, `style rule for ${selector} must exist`)
  return match[0]
}

test('Smart Insights uses the same 1480px workspace viewport as Mock Portfolio', () => {
  const smartRule = styleRule(smartInsightsSource, '.legacy-main')
  const portfolioRule = styleRule(mockPortfolioSource, '.workspace-header, .page-alert, .paper-boundary, .portfolio-hero, .holdings-card, .risk-section, .transaction-card')

  assert.match(portfolioRule, /max-width:\s*1480px/u)
  assert.match(smartRule, /max-width:\s*1480px/u)
  assert.match(smartRule, /box-sizing:\s*border-box/u)
})
