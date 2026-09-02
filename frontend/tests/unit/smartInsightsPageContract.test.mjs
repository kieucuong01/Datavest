import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
const opinionsSource = fs.readFileSync(new URL('../../src/views/smart-insights/components/AssetOpinionsSection.vue', import.meta.url), 'utf8')
const routerSource = fs.readFileSync(new URL('../../src/config/router.config.js', import.meta.url), 'utf8')

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
