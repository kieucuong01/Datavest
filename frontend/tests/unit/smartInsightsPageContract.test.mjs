import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
const opinionsSource = fs.readFileSync(new URL('../../src/views/smart-insights/components/AssetOpinionsSection.vue', import.meta.url), 'utf8')
const apiSource = fs.readFileSync(new URL('../../src/api/smart-insights.js', import.meta.url), 'utf8')
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

test('Asset Opinions combines common assets with the account watchlist through safe shared report state', () => {
  assert.match(apiSource, /hasAccessToken/u)
  assert.match(apiSource, /\/api\/smart-insights\/overview/u)
  assert.match(source, /response\.data\.assets/u)
  assert.match(source, /buildAccountOpinionRows/u)
  assert.match(source, /getSharedResearchReports/u)
  assert.match(source, /applySharedResearchStates/u)
  assert.match(source, /buildSharedOpinionRows/u)
  assert.match(opinionsSource, /guest/u)
})

test('Guest Asset Opinions reads only public TradingAgents reports without a login redirect', () => {
  assert.match(apiSource, /getPublicResearchReport/u)
  assert.match(apiSource, /params:\s*\{\s*lang:\s*'vi-VN'\s*\}/u)
  assert.match(source, /loadPublicDeepReports/u)
  assert.match(source, /getPublicResearchReport\(row\.publicAssetKey, 'deep'\)/u)
  assert.doesNotMatch(source, /isGuest && mode === 'deep'[\s\S]{0,180}openAuthModal/u)
  assert.match(source, /public-deep-report/u)
  assert.match(source, /<report-pdf-reader[\s\S]*:public-asset-key="isGuest \? selectedOpinionRow\.publicAssetKey : ''"/u)
  assert.match(source, /:shared-asset-key="!isGuest \? selectedOpinionRow\.sharedResearchAssetKey : ''"/u)
  assert.match(source, /publicDeepReportView:\s*'full'/u)
  assert.match(source, /v-model="publicDeepReportView"/u)
  assert.match(source, /:variant="publicDeepReportView"/u)
  assert.match(apiSource, /getPublicResearchReportSummaryPdf/u)
  assert.doesNotMatch(source, /<pre>\{\{ publicDeepReport\.body \}\}<\/pre>/u)
  assert.doesNotMatch(opinionsSource, /guest \? 'lock' : 'apartment'/u)
})

test('Smart Insights page has no BTC Forecast or Kronos surface', () => {
  assert.doesNotMatch(source, /forecast|kronos|btcBottom/iu)
})

test('MVP hides the Indicator Community route and keeps evidence provenance for Market Pulse', () => {
  assert.doesNotMatch(routerSource, /path:\s*['"]\/indicator-community['"]/u)
  assert.match(source, /evidence\.sourceUrl/u)
  assert.match(source, /evidence\.reliability/u)
})

test('Asset Opinions only renders a TradingAgents report pinned to its row', () => {
  assert.match(opinionsSource, /row\.deepState\.report/u)
  assert.match(opinionsSource, /reportPreview\(row\)/u)
  assert.doesNotMatch(opinionsSource, /row\.opinion/u)
})

test('Asset Opinions does not show the retired Smart Insights quantitative score', () => {
  assert.doesNotMatch(opinionsSource, /quantScore/u)
  assert.doesNotMatch(opinionsSource, /displayScore/u)
})

test('Asset Opinions shows the Portfolio Manager decision summary instead of a raw generated timestamp', () => {
  assert.match(opinionsSource, /extractPortfolioManagerDecisionSummary/u)
  assert.match(opinionsSource, /decisionSummary\(row\)/u)
  assert.match(opinionsSource, /smartInsights\.rating/u)
  assert.match(opinionsSource, /smartInsights\.timeHorizon/u)
  assert.match(opinionsSource, /smartInsights\.reportCreatedAt/u)
  assert.doesNotMatch(opinionsSource, /Generated:/u)
})

test('Asset Opinions treats the latest TradingAgents report as available even without a directional rating', () => {
  assert.match(opinionsSource, /reportDecisionLabel\(row\)/u)
  assert.match(opinionsSource, /reportPreview\(row\)/u)
  assert.match(opinionsSource, /if \(this\.researchReport\(row\)\) return \{ status: 'AVAILABLE'/u)
  assert.match(opinionsSource, /smartInsights\.viewDeepReport/u)
  assert.match(opinionsSource, /smartInsights\.createDeepReport/u)
})

test('Asset Opinions presents a clear decision hierarchy instead of a dense text row', () => {
  assert.match(opinionsSource, /class="opinion-main"/u)
  assert.match(opinionsSource, /class="decision-summary-facts"/u)
  assert.match(opinionsSource, /decisionActionRows\(row\)/u)
  assert.match(opinionsSource, /class="decision-summary-action"/u)
  assert.match(opinionsSource, /smartInsights\.overweight/u)
  assert.match(opinionsSource, /smartInsights\.underweight/u)
  assert.match(opinionsSource, /class="opinion-column-label"/u)
  assert.match(opinionsSource, /class="opinion-meta"/u)
  assert.match(opinionsSource, /class="status-label"/u)
  assert.match(opinionsSource, /class="status-indicator"/u)
  assert.match(opinionsSource, /class="opinion-actions"[\s\S]*?deep-analysis-action/u)
  assert.doesNotMatch(opinionsSource, /quick-analysis-action/u)
})

test('Asset Opinions shows the full decision brief without redundant state labels', () => {
  assert.match(opinionsSource, /class="decision-summary-facts"/u)
  assert.match(opinionsSource, /class="decision-summary-fact-label"/u)
  assert.match(opinionsSource, /row\.symbol \|\| row\.displaySymbol/u)
  assert.match(opinionsSource, /decisionSummary\(row\)\.timeHorizon/u)
  assert.doesNotMatch(opinionsSource, /\{\{\s*\$t\('smartInsights\.reportUnavailable'\)\s*\}\}/u)
  assert.doesNotMatch(opinionsSource, /\{\{\s*\$t\('smartInsights\.decisionSummary'\)\s*\}\}/u)
  assert.doesNotMatch(opinionsSource, /\{\{\s*\$t\('smartInsights\.deepEngine'\)\s*\}\}/u)
})

test('Smart Insights has a translated rating label for the decision facts', () => {
  const localeSource = fs.readFileSync(new URL('../../src/locales/smart-insights.js', import.meta.url), 'utf8')
  assert.match(localeSource, /'smartInsights\.rating':\s*'Rating'/u)
  assert.match(localeSource, /'smartInsights\.rating':\s*'Xếp hạng'/u)
})

test('Asset Opinions keeps its single TradingAgents action usable on phones', () => {
  assert.match(opinionsSource, /@media \(max-width: 680px\)[\s\S]*?\.opinion-actions\s*\{[\s\S]*?grid-template-columns:\s*1fr/u)
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

test('Guest Smart Insights hides readiness and the retired guest alert', () => {
  assert.doesNotMatch(source, /class="guest-mode-alert"/u)
  assert.match(source, /<section v-if="!isGuest" class="data-readiness"/u)
})

test('Header logo links back to Smart Insights', () => {
  assert.match(layoutSource, /href="#\/smart-insights"/u)
  assert.match(layoutSource, /goSmartInsights/u)
})

test('Mobile navigation centers the trigger and uses a light drawer surface', () => {
  assert.match(layoutStyles, /@media \(max-width: 768px\)[\s\S]*?\.basic-layout-wrapper \.ant-pro-global-header-trigger[\s\S]*?display:\s*inline-flex\s*!important[\s\S]*?justify-content:\s*center\s*!important/u)
  assert.match(layoutSource, /@media \(max-width: 768px\)[\s\S]*?\.ant-drawer\.ant-pro-sider-menu\.ant-drawer-open[\s\S]*?background:\s*#f8fafc\s*!important/u)
  assert.match(layoutSource, /\.ant-drawer\.ant-pro-sider-menu\.ant-drawer-open[\s\S]*?\.ant-menu-dark[\s\S]*?background:\s*transparent\s*!important/u)
})
