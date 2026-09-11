import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
const opinionsSource = fs.readFileSync(new URL('../../src/views/smart-insights/components/AssetOpinionsSection.vue', import.meta.url), 'utf8')
const routerSource = fs.readFileSync(new URL('../../src/config/router.config.js', import.meta.url), 'utf8')
const layoutSource = fs.readFileSync(new URL('../../src/layouts/BasicLayout.vue', import.meta.url), 'utf8')
const layoutStyles = fs.readFileSync(new URL('../../src/layouts/BasicLayout.less', import.meta.url), 'utf8')

test('Smart Insights page removes the legacy header and portfolio changes card', () => {
  assert.doesNotMatch(source, /legacy-header/u)
  assert.doesNotMatch(source, /portfolio-changes/u)
})

test('Smart Insights viewport matches the Mock Portfolio workspace treatment', () => {
  assert.match(source, /\.legacy-main\s*\{[^}]*width:\s*100%[^}]*max-width:\s*1480px[^}]*box-sizing:\s*border-box/isu)
  assert.doesNotMatch(source, /@media[^{]*\{[^}]*\.legacy-main\s*\{\s*width:\s*calc\(100%\s*-\s*24px\)/isu)
})

test('Asset Opinions is sourced from the AI Assistant watchlist', () => {
  assert.match(source, /getWatchlist/u)
  assert.match(source, /buildWatchlistOpinionRows/u)
  assert.match(opinionsSource, /\/ai-asset-analysis/u)
})

test('Smart Insights page has no BTC Forecast or Kronos surface', () => {
  assert.doesNotMatch(source, /forecast|kronos|btcBottom/iu)
})

test('MVP hides the Indicator Community route and keeps evidence provenance for Market Pulse', () => {
  assert.doesNotMatch(routerSource, /path:\s*['"]\/indicator-community['"]/u)
  assert.match(source, /evidence\.sourceUrl/u)
  assert.match(source, /evidence\.reliability/u)
})

test('Asset Opinions only renders an AI Assistant report pinned to its row', () => {
  assert.match(opinionsSource, /row\.report/u)
  assert.match(opinionsSource, /row\.report\.summary/u)
  assert.doesNotMatch(opinionsSource, /row\.opinion/u)
})

test('Asset Opinions does not show the retired Smart Insights quantitative score', () => {
  assert.doesNotMatch(opinionsSource, /quantScore/u)
  assert.doesNotMatch(opinionsSource, /displayScore/u)
})

test('Asset Opinions identifies the AI Assistant decision and report timestamp', () => {
  assert.match(opinionsSource, /decisionTone\(row\.report\.decision\)/u)
  assert.match(opinionsSource, /formatDateTime\(row\.report\.createdAt\)/u)
})

test('Asset Opinions presents a clear decision hierarchy instead of a dense text row', () => {
  assert.match(opinionsSource, /class="opinion-main"/u)
  assert.match(opinionsSource, /class="opinion-column-label"/u)
  assert.match(opinionsSource, /class="opinion-meta"/u)
  assert.match(opinionsSource, /class="status-label"/u)
  assert.match(opinionsSource, /class="status-indicator"/u)
  assert.match(opinionsSource, /class="opinion-actions"[\s\S]*?quick-analysis-action[\s\S]*?deep-analysis-action/u)
})

test('Asset Opinions uses two touch actions on phones and stacks them on narrow screens', () => {
  assert.match(opinionsSource, /@media \(max-width: 680px\)[\s\S]*?\.opinion-actions\s*\{[\s\S]*?display:\s*grid[\s\S]*?grid-template-columns:\s*repeat\(2/u)
  assert.match(opinionsSource, /@media \(max-width: 380px\)[\s\S]*?\.opinion-actions\s*\{[\s\S]*?grid-template-columns:\s*1fr/u)
  assert.match(opinionsSource, /\.opinion-actions \.ant-btn\s*\{[\s\S]*?min-height:\s*44px/u)
})

test('Smart Insights formats dates in Vietnam time and guards stale date responses', () => {
  assert.match(source, /formatVietnamDate/u)
  assert.match(source, /formatVietnamDateTime/u)
  assert.match(source, /requestSequence/u)
  assert.match(source, /isCurrentRequest/u)
  assert.doesNotMatch(source, /new Date\(\)\.toISOString\(\)\.slice\(0, 10\)/u)
})

test('Smart Insights exposes a compact data readiness bar with per-section retry actions', () => {
  assert.match(source, /data-readiness/u)
  assert.match(source, /retrySection/u)
  assert.match(source, /dataHealth/u)
  assert.match(source, /fetchedAt/u)
  assert.match(source, /freshness/u)
  assert.match(source, /coverage/u)
})

test('Smart Insights removes the retired daily hero and decision brief surfaces', () => {
  assert.doesNotMatch(source, /<section class="daily-hero"/u)
  assert.doesNotMatch(source, /decision-brief-card|decision-brief-title/u)
  assert.doesNotMatch(source, /data-readiness-title/u)
  assert.match(source, /class="data-readiness"/u)
})

test('Mobile navigation centers the trigger and uses a light drawer surface', () => {
  assert.match(layoutStyles, /@media \(max-width: 768px\)[\s\S]*?\.basic-layout-wrapper \.ant-pro-global-header-trigger[\s\S]*?display:\s*inline-flex\s*!important[\s\S]*?justify-content:\s*center\s*!important/u)
  assert.match(layoutSource, /@media \(max-width: 768px\)[\s\S]*?\.ant-drawer\.ant-pro-sider-menu\.ant-drawer-open[\s\S]*?background:\s*#f8fafc\s*!important/u)
  assert.match(layoutSource, /\.ant-drawer\.ant-pro-sider-menu\.ant-drawer-open[\s\S]*?\.ant-menu-dark[\s\S]*?background:\s*transparent\s*!important/u)
})
