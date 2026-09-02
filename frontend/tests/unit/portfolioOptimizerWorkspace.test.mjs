import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => readFileSync(path.join(root, relative), 'utf8')
const exists = relative => existsSync(path.join(root, relative))

test('portfolio optimizer API keeps preview and apply as separate paper steps', () => {
  const source = read('src/api/portfolio-optimizer.js')
  assert.match(source, /\/api\/portfolio\/optimizer\/runs/)
  assert.match(source, /\/preview/)
  assert.match(source, /\/apply/)
  assert.doesNotMatch(source, /broker|live.order|credential/i)
})

test('portfolio optimizer workspace is reachable and labels apply as simulated', () => {
  const router = read('src/config/router.config.js')
  const view = read('src/views/portfolio-optimizer/index.vue')
  assert.match(router, /path: '\/portfolio-optimizer'/)
  assert.match(view, /SIMULATED/)
  assert.match(view, /previewOptimizerRun/)
  assert.match(view, /applyOptimizerRun/)
  assert.match(view, /inputChecksum/)
})

test('portfolio optimizer has English and Vietnamese product copy', () => {
  const messages = read('src/locales/portfolio-optimizer.js')
  assert.match(messages, /'en-US'/)
  assert.match(messages, /'vi-VN'/)
  assert.match(messages, /Tối ưu danh mục/)
  assert.match(messages, /LIVE data only/)
})

test('active product routes and research workspaces do not load removed execution surfaces', () => {
  const router = read('src/config/router.config.js')
  const layout = read('src/layouts/BasicLayout.vue')
  const bootstrap = read('src/core/bootstrap.js')
  const store = read('src/store/index.js')
  const getters = read('src/store/getters.js')
  const indicatorIde = read('src/views/indicator-ide/index.vue')
  const aiWorkspace = read('src/views/ai-asset-analysis/index.vue')
  const strategyIde = read('src/views/strategy-ide/index.vue')
  const avatar = read('src/components/GlobalHeader/AvatarDropdown.vue')

  for (const forbidden of ['broker-accounts', "path: '/billing'", 'agent-tokens', 'strategy-center', 'user-manage']) {
    assert.ok(!router.includes(forbidden), forbidden)
  }
  assert.doesNotMatch(`${indicatorIde}\n${aiWorkspace}`, /import QuickTradePanel|<quick-trade-panel/)
  assert.doesNotMatch(strategyIde, /ExecutorStrategies|executor-strategies/)
  assert.doesNotMatch(avatar, /getMembershipPlans|handleBilling|account-recharge|account-credits/)
  assert.doesNotMatch(layout, /MenuGroupLiveMonitor|menu\.dashboard\.strategyCenter/)
  assert.match(layout, /path: '\/menu-group\/quant-lab'/)
  assert.match(layout, /paths: \['\/portfolio-optimizer', '\/strategy-ide', '\/backtest-center'\]/)
  assert.doesNotMatch(layout, /path: '\/menu-group\/(strategy-lab|backtest-center)'/)
  assert.doesNotMatch(`${bootstrap}\n${store}\n${getters}`, /BrokerMarketPolicy|brokerMarketPolicy|modules\/policy/)
  assert.equal(exists('src/api/policy.js'), false)
  assert.equal(exists('src/store/modules/policy.js'), false)
})

test('Smart Insights exposes its history-backed overview and keeps Market Pulse evidence', () => {
  const api = read('src/api/smart-insights.js')
  const view = read('src/views/smart-insights/index.vue')
  const router = read('src/config/router.config.js')

  assert.match(api, /\/api\/smart-insights\/overview/)
  assert.match(api, /\/api\/smart-insights\/evidence\//)
  assert.match(api, /\/api\/smart-insights\/data-health/)
  assert.match(view, /dailyBrief/)
  assert.doesNotMatch(view, /mode === 'demo'/)
  assert.match(view, /openEvidence/)
  assert.match(router, /path: '\/smart-insights'/)
})
