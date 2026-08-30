import assert from 'node:assert/strict'
import { execFileSync, spawnSync } from 'node:child_process'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { existsSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

import { UPSTREAM_SHA, buildInventory } from '../../scripts/datavest-scope-inventory.mjs'

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

const preservedGroups = [
  'market_data',
  'indicator_ide',
  'alerts',
  'backtest',
  'strategy_research',
  'factor_research',
  'ai_analysis',
  'paper_portfolio',
  'free_library'
]

const forbiddenGroups = [
  'broker_credentials',
  'live_orders',
  'trading_worker',
  'live_strategy_deploy',
  'agent_trading_scope',
  'grid_copy_trading',
  'billing_credits',
  'paid_hidden_marketplace',
  'mobile'
]

test('scope inventory has an exact safe schema and semantic controls', () => {
  const inventory = buildInventory(repositoryRoot)
  const inspected = new Set(inventory.inspectedFiles)

  assert.deepEqual(Object.keys(inventory), ['sourceBaselines', 'inspectedFiles', 'preservedHits', 'forbiddenHits'])
  assert.equal(UPSTREAM_SHA, '6f9ce97fe4730355c39a72610f5dbda3f05d3db7')
  assert.deepEqual(inventory.sourceBaselines, {
    frontendTaskBase: '6f9ce97fe4730355c39a72610f5dbda3f05d3db7',
    frontendUpstream: '6f9ce97fe4730355c39a72610f5dbda3f05d3db7'
  })
  assert.deepEqual(inventory.inspectedFiles, [...inspected].sort())
  assert.ok(inventory.inspectedFiles.every((file) => typeof file === 'string' && file.startsWith('src/') && !path.isAbsolute(file) && !file.includes('\\')))
  assert.deepEqual(Object.keys(inventory.preservedHits), preservedGroups)
  assert.deepEqual(Object.keys(inventory.forbiddenHits), forbiddenGroups)

  for (const groups of [inventory.preservedHits, inventory.forbiddenHits]) {
    for (const files of Object.values(groups)) {
      assert.deepEqual(files, [...files].sort())
      assert.ok(files.every((file) => typeof file === 'string' && inspected.has(file)))
    }
  }

  assert.ok(inventory.preservedHits.backtest.includes('src/views/backtest-center/PortfolioResult.vue'))
  assert.ok(inventory.preservedHits.ai_analysis.includes('src/views/ai-analysis/index.vue'))
  for (const group of forbiddenGroups) {
    assert.deepEqual(inventory.forbiddenHits[group], [], group)
  }

  assert.ok(!inventory.forbiddenHits.grid_copy_trading.includes('src/views/backtest-center/PortfolioResult.vue'))
  assert.ok(!inventory.forbiddenHits.mobile.includes('src/layouts/BasicLayout.vue'))
  assert.ok(!inventory.forbiddenHits.agent_trading_scope.includes('src/views/ai-analysis/index.vue'))
  assert.ok(!inventory.forbiddenHits.live_strategy_deploy.includes('src/views/strategy-ide/index.vue'))
  assert.ok(!inventory.forbiddenHits.paid_hidden_marketplace.includes('src/views/indicator-community/components/OverfitRiskGauge.vue'))
  assert.ok(!inventory.forbiddenHits.broker_credentials.includes('src/views/ai-analysis/components/CopilotWorkbench.vue'))
  assert.ok(!inventory.forbiddenHits.broker_credentials.includes('src/views/indicator-ide/index.vue'))
})

test('scope inventory ignores an untracked local Vue file', () => {
  const relativePath = 'src/views/LocalScopeProbe.vue'
  const localFile = path.join(repositoryRoot, relativePath)
  writeFileSync(localFile, '<template>quick trade broker grid mobile</template>')
  try {
    const inventory = buildInventory(repositoryRoot)
    assert.ok(!inventory.inspectedFiles.includes(relativePath))
    assert.ok(Object.values(inventory.forbiddenHits).every((files) => !files.includes(relativePath)))
  } finally {
    unlinkSync(localFile)
  }
})

test('all retired product surfaces are physically absent from the frontend inventory', () => {
  const inventory = buildInventory(repositoryRoot)
  for (const group of forbiddenGroups) assert.deepEqual(inventory.forbiddenHits[group], [], group)
})

test('broker credential and quick-order sources are physically absent', () => {
  const hits = new Set(buildInventory(repositoryRoot).forbiddenHits.broker_credentials)
  assert.equal(hits.size, 0)
  assert.deepEqual(buildInventory(repositoryRoot).forbiddenHits.live_orders, [])
})

test('production source cannot reach retired billing or broker account surfaces', () => {
  const sourceFiles = execFileSync('git', ['ls-files', '-z', '--', 'src'], {
    cwd: repositoryRoot,
    encoding: 'utf8'
  }).split('\0').filter(Boolean)
    .filter((file) => /\.(?:js|jsx|vue)$/.test(file))
    .filter((file) => existsSync(path.join(repositoryRoot, file)))

  const forbiddenContracts = [
    '@/api/billing',
    '/api/billing',
    "'/billing'",
    "\"/billing\"",
    "'/broker-accounts'",
    "\"/broker-accounts\"",
    '/strategy-center',
    '/api/strategies/executors',
    '/api/strategies/grid-resting-orders',
    '/api/users/system-strategies',
    '/api/agent/v1/admin/tokens',
    '/api/users/my-credits-log',
    '/api/users/set-credits',
    '/api/users/credits-log',
    "tab: 'credits'",
    "key: 'credits'",
    'getMyCreditsLog',
    'setUserCredits',
    'getUserCreditsLog',
    'creditsModalVisible',
    'creditsLogPagination',
    'normalizeInsufficientCreditsError',
    'insufficientCreditsError',
    "msg === 'Insufficient credits'",
    'aiCopilot.preflight.creditsTitle',
    'aiCopilot.preflight.creditsMessage',
    'aiCopilot.setup.action.billing',
    'aiCopilot.setup.action.credits',
    'aiCopilot.setup.billing.title',
    'aiCopilot.setup.billing.body'
  ]
  const hits = []
  for (const file of sourceFiles) {
    const source = readFileSync(path.join(repositoryRoot, file), 'utf8')
    for (const contract of forbiddenContracts) {
      if (source.includes(contract)) hits.push(`${file}: ${contract}`)
    }
  }

  assert.deepEqual(hits, [])
  assert.equal(existsSync(path.join(repositoryRoot, 'src/api/billing.js')), false)

  const router = readFileSync(path.join(repositoryRoot, 'src/config/router.config.js'), 'utf8')
  const aiAnalysis = readFileSync(path.join(repositoryRoot, 'src/views/ai-analysis/index.vue'), 'utf8')
  const fastReport = readFileSync(path.join(repositoryRoot, 'src/views/ai-analysis/components/FastAnalysisReport.vue'), 'utf8')
  const copilot = readFileSync(path.join(repositoryRoot, 'src/views/ai-analysis/components/CopilotWorkbench.vue'), 'utf8')
  assert.match(router, /path:\s*['"]\/ai-analysis(?:\/|['"])/)
  assert.match(aiAnalysis, /import CopilotWorkbench from/)
  assert.doesNotMatch(aiAnalysis, /analysis(?:Submitted|Complete)WithCredits|formatCreditNum/)
  assert.doesNotMatch(fastReport, /insufficientCreditsError/)
  assert.doesNotMatch(copilot, /aiCopilot\.preflight\.credits|setupAction\(['"]credits['"]\)/)
  assert.match(copilot, /filter\(item => !this\.isRetiredBillingPreflightItem\(item\)\)/)
})

test('test:unit executes the complete unit-test inventory', () => {
  const packageJson = JSON.parse(readFileSync(path.join(repositoryRoot, 'package.json'), 'utf8'))

  assert.equal(packageJson.scripts['test:unit'], 'node --test tests/unit/*.test.mjs')
})

test('scope inventory fails clearly when tracked-file enumeration is unavailable', () => {
  const missingCheckout = path.join(repositoryRoot, 'tests', 'unit', 'not-a-git-checkout')
  assert.throws(() => buildInventory(missingCheckout), /Unable to enumerate tracked files/)
})

test('tracked-file enumeration failure does not leak the checkout path', () => {
  const moduleUrl = pathToFileURL(path.join(repositoryRoot, 'scripts', 'datavest-scope-inventory.mjs')).href
  const probe = `import { buildInventory } from ${JSON.stringify(moduleUrl)}; try { buildInventory('not-a-checkout') } catch (error) { process.stderr.write(error.message); process.exit(1) }`
  const result = spawnSync(process.execPath, ['--input-type=module', '--eval', probe], { encoding: 'utf8' })

  assert.equal(result.status, 1)
  assert.equal(result.stderr, 'Unable to enumerate tracked files with git ls-files')
  assert.ok(!result.stderr.includes(repositoryRoot))
})

test('scope inventory command emits the reviewable JSON artifact', () => {
  const stdout = execFileSync(process.execPath, ['scripts/datavest-scope-inventory.mjs'], {
    cwd: repositoryRoot,
    encoding: 'utf8'
  })

  assert.deepEqual(JSON.parse(stdout), buildInventory(repositoryRoot))
})
