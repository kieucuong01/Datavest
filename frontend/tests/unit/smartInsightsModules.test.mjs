import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const modulePath = path.join(repositoryRoot, 'src/views/smart-insights/overviewModules.js')

async function loadModuleBuilder () {
  assert.equal(existsSync(modulePath), true, 'Smart Insights overview module mapper must exist')
  return import(pathToFileURL(modulePath).href)
}

test('live crypto overview maps only source-backed fields into the three insight modules', async () => {
  const { buildOverviewModules, UNAVAILABLE } = await loadModuleBuilder()
  const overview = {
    id: 'snapshot-live-1',
    asOf: '2026-08-24T12:00:00+00:00',
    market: 'crypto',
    mode: 'live',
    status: 'COMPLETE',
    methodologyVersion: 'datavest-smart-insights-v1',
    evidenceChecksum: 'abc123',
    summary: {
      sourceCount: 2,
      metricCount: 3,
      observationCount: 4,
      sources: ['openbb-deribit', 'mempool-space'],
      metrics: ['crypto.derivatives.basis', 'crypto.mempool.count'],
      directionalModelStatus: 'UNAVAILABLE'
    }
  }

  const modules = buildOverviewModules(overview)

  assert.deepEqual(modules.decisionBrief, {
    available: true,
    status: 'COMPLETE',
    asOf: '2026-08-24T12:00:00+00:00',
    methodologyVersion: 'datavest-smart-insights-v1',
    directionalModelStatus: 'UNAVAILABLE',
    evidenceChecksum: 'abc123',
    sourceCount: 2,
    metricCount: 3,
    observationCount: 4
  })
  assert.deepEqual(modules.pulse, {
    available: true,
    market: 'crypto',
    sources: ['openbb-deribit', 'mempool-space'],
    metrics: ['crypto.derivatives.basis', 'crypto.mempool.count'],
    observationCount: 4
  })
  assert.deepEqual(modules.portfolioImpact, { available: false, status: UNAVAILABLE })
})

test('demo macro overview preserves its explicit demo data without adding live or invented values', async () => {
  const { buildOverviewModules } = await loadModuleBuilder()
  const overview = {
    asOf: '2026-08-24T13:00:00+00:00',
    market: 'macro',
    mode: 'demo',
    status: 'PARTIAL',
    methodologyVersion: 'demo-method',
    evidenceChecksum: 'demo-checksum',
    summary: {
      sourceCount: 1,
      metricCount: 1,
      observationCount: 1,
      sources: ['demo-fred'],
      metrics: ['macro.demo.rate'],
      directionalModelStatus: 'UNAVAILABLE'
    }
  }

  const modules = buildOverviewModules(overview)

  assert.equal(modules.decisionBrief.status, 'PARTIAL')
  assert.deepEqual(modules.pulse.sources, ['demo-fred'])
  assert.deepEqual(modules.pulse.metrics, ['macro.demo.rate'])
  assert.equal(modules.pulse.observationCount, 1)
  assert.equal(modules.portfolioImpact.available, false)
})

test('missing or unsupported overview data is explicitly unavailable', async () => {
  const { buildOverviewModules, UNAVAILABLE } = await loadModuleBuilder()

  assert.deepEqual(buildOverviewModules(null), {
    decisionBrief: { available: false, status: UNAVAILABLE },
    pulse: { available: false, status: UNAVAILABLE },
    portfolioImpact: { available: false, status: UNAVAILABLE }
  })

  const modules = buildOverviewModules({ status: 'COMPLETE', market: 'all', summary: {} })
  assert.equal(modules.decisionBrief.available, true)
  assert.equal(modules.decisionBrief.asOf, UNAVAILABLE)
  assert.equal(modules.decisionBrief.directionalModelStatus, UNAVAILABLE)
  assert.deepEqual(modules.pulse, { available: false, status: UNAVAILABLE })
  assert.deepEqual(modules.portfolioImpact, { available: false, status: UNAVAILABLE })
})

test('Smart Insights view and VI/EN messages expose every required module and unavailable state', async () => {
  const component = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/index.vue'), 'utf8')
  const layout = readFileSync(path.join(repositoryRoot, 'src/layouts/BasicLayout.vue'), 'utf8')
  const opinions = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/AssetOpinionsSection.vue'), 'utf8')
  const pulse = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/MarketPulseSection.vue'), 'utf8')
  const liveSources = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/LiveDataSources.vue'), 'utf8')
  const surfaces = `${component}\n${opinions}\n${pulse}\n${liveSources}`
  const messages = (await import(pathToFileURL(path.join(repositoryRoot, 'src/locales/smart-insights.js')).href)).default
  const keys = [
    'smartInsights.opinions',
    'smartInsights.marketRhythm',
    'smartInsights.liveDataSources',
    'smartInsights.none',
    'smartInsights.never',
    'smartInsights.notAvailable',
    'smartInsights.checksum'
  ]

  for (const key of keys) {
    assert.match(surfaces, new RegExp(key.replace('.', '\\.'), 'u'))
    assert.equal(typeof messages['en-US'][key], 'string')
    assert.equal(typeof messages['vi-VN'][key], 'string')
    assert.ok(messages['en-US'][key].trim())
    assert.ok(messages['vi-VN'][key].trim())
  }
  assert.match(component, /buildOverviewModules/)
  assert.match(layout, /normalizeLiveAssetRows/)
  assert.match(opinions, /smartInsights\.opinions/)
  assert.match(pulse, /smartInsights\.marketRhythm/)
  assert.match(component, /demo-watermark/)
  assert.match(component, /openEvidence/)
  assert.match(component, /healthVisible/)
  assert.doesNotMatch(component, />None</)
  assert.doesNotMatch(component, /'NEVER'/)
  assert.doesNotMatch(component, /'N\/A'/)
  assert.doesNotMatch(component, />Checksum:</)
})

test('Smart Insights opens on the full production-style overview with the crypto pulse loaded', async () => {
  const component = readFileSync(modulePath.replace('overviewModules.js', 'index.vue'), 'utf8')
  assert.match(component, /market:\s*'all'/u)
  assert.match(component, /cryptoPulse/u)
  assert.match(component, /MarketPulseSection/u)
})

test('Smart Insights renders the DataVest page shell and replaces removed legacy surfaces', async () => {
  const component = readFileSync(modulePath.replace('overviewModules.js', 'index.vue'), 'utf8')
  const opinions = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/AssetOpinionsSection.vue'), 'utf8')
  const pulse = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/MarketPulseSection.vue'), 'utf8')
  for (const className of [
    'legacy-page',
    'daily-hero',
    'crypto-calendar',
    'legacy-footer'
  ]) {
    assert.match(component, new RegExp(`class="[^"]*${className}`, 'u'))
  }
  assert.match(opinions, /class="[^"]*asset-opinions/u)
  assert.match(pulse, /class="[^"]*market-pulse/u)
  assert.doesNotMatch(component, /legacy-header|legacy-ticker|portfolio-changes/u)
  assert.match(component, /smartInsights\.legacyHeroTitle/u)
  assert.match(component, /smartInsights\.dataUnavailable/u)
})

test('Smart Insights binds the source-backed crypto pulse contract to the seven-tab component', async () => {
  const component = readFileSync(modulePath.replace('overviewModules.js', 'index.vue'), 'utf8')
  const api = readFileSync(path.join(repositoryRoot, 'src/api/smart-insights.js'), 'utf8')
  assert.match(api, /getSmartInsightsCryptoPulse/u)
  assert.match(component, /getSmartInsightsCryptoPulse/u)
  assert.match(component, /loadPulse/u)
  assert.match(component, /MarketPulseSection/u)
  assert.doesNotMatch(component, /btcBottom|Kronos/u)
})

test('Smart Insights renders imported production fields and real chart primitives', async () => {
  const component = readFileSync(modulePath.replace('overviewModules.js', 'index.vue'), 'utf8')
  const opinions = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/AssetOpinionsSection.vue'), 'utf8')
  const chart = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/PulseTrendChart.vue'), 'utf8')
  assert.match(component, /riskAlerts/u)
  assert.match(opinions, /row\.opinion\.score/u)
  assert.match(opinions, /evidenceValidated/u)
  assert.doesNotMatch(opinions, /portfolioWeightPct/u)
  assert.match(chart, /<svg/u)
  assert.match(component, /MarketPulseSection/u)
  assert.doesNotMatch(`${component}${chart}`, /gauge-placeholder|large-chart-placeholder/u)
})

test('Smart Insights exposes imported portfolio impact when the production briefing supplies it', async () => {
  const { buildOverviewModules } = await loadModuleBuilder()
  const modules = buildOverviewModules({
    market: 'all',
    status: 'PARTIAL',
    summary: {},
    portfolioState: { currency: 'USD' },
    portfolioChanges: [{ symbol: 'BTC', changeType: 'increase' }]
  })

  assert.deepEqual(modules.portfolioImpact, {
    available: true,
    status: 'PARTIAL',
    changeCount: 1,
    stateAvailable: true
  })
})

test('Smart Insights selects the newest available analysis date on first load', async () => {
  const component = readFileSync(modulePath.replace('overviewModules.js', 'index.vue'), 'utf8')
  assert.match(component, /if \(!this\.asOf && this\.dates\.length\) this\.asOf = this\.dates\[0\]/u)
})
