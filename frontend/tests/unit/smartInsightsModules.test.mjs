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
  assert.match(chart, /from 'echarts'/u)
  assert.match(component, /MarketPulseSection/u)
  assert.doesNotMatch(`${component}${chart}`, /gauge-placeholder|large-chart-placeholder/u)
})

test('Smart Insights routes the flows tab to the multi-asset Flow Terminal instead of CoinShares', async () => {
  const pulse = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/MarketPulseSection.vue'), 'utf8')
  const flowTerminal = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/FlowTerminal.vue'), 'utf8')

  assert.match(pulse, /FlowTerminal/u)
  assert.doesNotMatch(pulse, /coinshares-fund-flow/u)
  assert.match(flowTerminal, /assetOptions/u)
  assert.match(flowTerminal, /tooltip:\s*\{/u)
  assert.match(flowTerminal, /cumulative \? 'line' : 'bar'/u)
  assert.match(flowTerminal, /tableRows/u)
})

test('Smart Insights history tables show about ten rows before scrolling', () => {
  const flowTerminal = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/FlowTerminal.vue'), 'utf8')
  const derivativesTerminal = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/DerivativesTerminal.vue'), 'utf8')

  for (const source of [flowTerminal, derivativesTerminal]) {
    assert.match(source, /max-height:\s*3\d\dpx/u)
    assert.match(source, /overflow:\s*auto/u)
    assert.match(source, /position:\s*sticky/u)
  }
})

test('Smart Insights routes Cycle to a source-backed Altseason and CBBI terminal', () => {
  const pulse = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/MarketPulseSection.vue'), 'utf8')
  const cycleTerminalPath = path.join(repositoryRoot, 'src/views/smart-insights/components/CycleTerminal.vue')

  assert.equal(existsSync(cycleTerminalPath), true)
  const cycleTerminal = readFileSync(cycleTerminalPath, 'utf8')
  assert.match(pulse, /CycleTerminal/u)
  assert.match(cycleTerminal, /altcoin_season\.index/u)
  assert.match(cycleTerminal, /cbbi\.component/u)
  assert.match(cycleTerminal, /markArea/u)
  assert.match(cycleTerminal, /tooltip:\s*\{/u)
  assert.match(cycleTerminal, /rangeOptions/u)
  assert.match(cycleTerminal, /cbbi-main-card/u)
  assert.match(cycleTerminal, /cbbi-component-grid/u)
  assert.match(cycleTerminal, /cbbiComponentOptions/u)
  assert.match(cycleTerminal, /renderComponentCharts/u)
  assert.match(cycleTerminal, /price-cycle-models/u)
  assert.match(cycleTerminal, /2-Year MA/u)
  assert.match(cycleTerminal, /200WMA/u)
  assert.match(cycleTerminal, /Power Law \/ Rainbow/u)
  assert.match(cycleTerminal, /Halving → Peak context/u)
  assert.match(cycleTerminal, /not a buy\/sell signal/u)
  assert.match(cycleTerminal, /full-width-card/u)
  assert.match(cycleTerminal, /altcoin-summary-row/u)
  assert.match(cycleTerminal, /grid-template-columns: repeat\(2/u)
  assert.match(cycleTerminal, /\.cycle-terminal\s*\{[^}]*width:\s*100%[^}]*max-width:\s*none/u)
  assert.match(cycleTerminal, /\.cycle-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/u)
  assert.match(cycleTerminal, /grid-column:\s*auto/u)
})

test('Smart Insights keeps crypto detail terminals without the removed summary and chart grid', () => {
  const pulse = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/MarketPulseSection.vue'), 'utf8')

  assert.match(pulse, /FlowTerminal/u)
  assert.match(pulse, /DerivativesTerminal/u)
  assert.match(pulse, /CycleTerminal/u)
  assert.match(pulse, /OnchainTerminal/u)
  assert.doesNotMatch(pulse, /cryptoPulseTitle|pulse-metric-grid--summary|pulse-chart-grid|chartCards/u)
})

test('Smart Insights gives Fear & Greed its own gauge, historical values, and range chart', () => {
  const pulse = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/MarketPulseSection.vue'), 'utf8')
  const fearGreed = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/FearGreedPanel.vue'), 'utf8')

  assert.match(pulse, /FearGreedPanel/u)
  assert.match(fearGreed, /type: 'gauge'/u)
  assert.match(fearGreed, /Historical/u)
  assert.match(fearGreed, /rangeOptions/u)
  assert.match(fearGreed, /tooltip:\s*\{/u)
})

test('Smart Insights routes On-chain to the four-group source-backed terminal', () => {
  const pulse = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/MarketPulseSection.vue'), 'utf8')
  const terminalPath = path.join(repositoryRoot, 'src/views/smart-insights/components/OnchainTerminal.vue')

  assert.equal(existsSync(terminalPath), true)
  const terminal = readFileSync(terminalPath, 'utf8')
  assert.match(pulse, /OnchainTerminal/u)
  assert.match(terminal, /valuation/u)
  assert.match(terminal, /holders/u)
  assert.match(terminal, /liquidity/u)
  assert.match(terminal, /network/u)
  assert.match(terminal, /tooltip:\s*\{/u)
  assert.match(terminal, /Nguồn chưa kết nối/u)
  assert.doesNotMatch(terminal, /crypto\.cycle\.cbbi/u)
})

test('Smart Insights ETF charts support ECharts hover tooltips, flow modes, and range controls', () => {
  const chart = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/PulseTrendChart.vue'), 'utf8')

  assert.match(chart, /tooltip:\s*\{/u)
  assert.match(chart, /rangeOptions/u)
  assert.match(chart, /cumulative/u)
  assert.match(chart, /ResizeObserver/u)
  assert.match(chart, /if \(!this\.interactive\) return this\.\$t\('smartInsights\.latestValue'\)/u)
  assert.doesNotMatch(chart, /<svg/u)
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
