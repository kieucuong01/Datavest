import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const layout = fs.readFileSync(new URL('../../src/layouts/BasicLayout.vue', import.meta.url), 'utf8')
const smartInsightsPage = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
const ticker = fs.readFileSync(new URL('../../src/views/smart-insights/components/LiveDataSources.vue', import.meta.url), 'utf8')

test('mounts one live data ticker in the shared authenticated layout', () => {
  assert.match(layout, /import LiveDataSources from '@\/views\/smart-insights\/components\/LiveDataSources'/u)
  assert.match(layout, /<live-data-sources[\s\S]*:rows="liveAssetRows"/u)
  assert.ok(layout.indexOf('<live-data-sources') < layout.indexOf('<multi-tab'))
  assert.ok(layout.indexOf('<live-data-sources') < layout.indexOf('<route-view'))
  assert.doesNotMatch(smartInsightsPage, /<live-data-sources/u)
})

test('renders a seamless animated ticker that pauses for interaction and reduced motion', () => {
  assert.match(ticker, /live-data-ticker-viewport/u)
  assert.match(ticker, /live-data-ticker-track/u)
  assert.match(ticker, /aria-hidden="true"/u)
  assert.match(ticker, /animation:\s*live-data-ticker-scroll/u)
  assert.match(ticker, /:hover/u)
  assert.match(ticker, /:focus-within/u)
  assert.match(ticker, /prefers-reduced-motion/u)
  assert.match(ticker, /overflow:\s*hidden/u)
})

test('does not present a zero change for an asset whose live price is unavailable', () => {
  assert.match(ticker, /item\.price === null \? '—' : signedPercent\(item\.changePercent\)/u)
})
