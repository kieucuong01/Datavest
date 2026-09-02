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

test('MVP hides the Indicator Community route and exposes evidence provenance', () => {
  assert.doesNotMatch(routerSource, /path:\s*['"]\/indicator-community['"]/u)
  assert.match(source, /evidence\.sourceUrl/u)
  assert.match(source, /evidence\.reliability/u)
})

test('Asset Opinions never renders unvalidated AI explanation text', () => {
  assert.match(opinionsSource, /evidenceValidated/u)
  assert.match(opinionsSource, /Array\.isArray\(row\.opinion\.evidence\)/u)
})

test('Asset Opinions only shows a quantitative score for validated evidence', () => {
  assert.match(
    opinionsSource,
    /row\.opinion && hasValidatedEvidence\(row\) \? displayScore\(row\.opinion\.score\) : \$t\('smartInsights\.notAvailable'\)/u
  )
})

test('Asset Opinions does not present an unvalidated stance or confidence as current research', () => {
  assert.match(opinionsSource, /<a-tag v-if="hasValidatedEvidence\(row\)"[^>]*:class="stanceTone\(row\.opinion\.stance\)"/u)
  assert.match(opinionsSource, /<small v-if="hasValidatedEvidence\(row\)" class="confidence-line">/u)
})
