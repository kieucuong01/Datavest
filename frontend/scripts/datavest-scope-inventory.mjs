import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

export const UPSTREAM_SHA = '6f9ce97fe4730355c39a72610f5dbda3f05d3db7'

const SOURCE_BASELINES = {
  frontendTaskBase: '6f9ce97fe4730355c39a72610f5dbda3f05d3db7',
  frontendUpstream: UPSTREAM_SHA
}

const PRESERVED_GROUPS = [
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

const FORBIDDEN_GROUPS = [
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

function trackedScopeFiles (repositoryRoot) {
  let output
  try {
    output = execFileSync('git', ['-C', repositoryRoot, 'ls-files', '-z', '--', 'src'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe']
    })
  } catch (error) {
    throw new Error('Unable to enumerate tracked files with git ls-files', { cause: error })
  }

  return output
    .split('\0')
    .filter(Boolean)
    .filter((file) => existsSync(path.join(repositoryRoot, file)))
    .filter((file) => file.endsWith('.vue') || file.startsWith('src/api/') || file.startsWith('src/router/') || file.startsWith('src/store/') || file === 'src/config/router.config.js')
    .sort()
}

function under (file, ...prefixes) {
  return prefixes.some((prefix) => file.startsWith(prefix))
}

function hasAll (source, ...contracts) {
  return contracts.every((contract) => source.includes(contract))
}

function preservedMatch (group, file, source) {
  const rules = {
    market_data: () => ['src/api/market.js', 'src/api/global-market.js'].includes(file) || under(file, 'src/views/global-market/', 'src/views/dashboard/'),
    indicator_ide: () => under(file, 'src/views/indicator-ide/') || (file === 'src/api/strategy.js' && source.includes('/api/indicator/')),
    alerts: () => file === 'src/api/portfolio.js' && source.includes('/api/portfolio/alerts'),
    backtest: () => under(file, 'src/views/backtest-center/') || (file === 'src/api/strategy.js' && source.includes('/api/backtest/')),
    strategy_research: () => under(file, 'src/views/strategy-ide/') || (file === 'src/api/strategy.js' && source.includes('/api/backtest/factor-research')),
    factor_research: () => file === 'src/api/factor.js' || under(file, 'src/views/strategy-ide/FactorLibrary'),
    ai_analysis: () => under(file, 'src/views/ai-analysis/'),
    paper_portfolio: () => file === 'src/api/portfolio.js' || file === 'src/views/backtest-center/PortfolioResult.vue',
    free_library: () => under(file, 'src/views/indicator-community/') || under(file, 'src/views/strategy-ide/UniverseLibrary')
  }
  return rules[group]()
}

function forbiddenMatch (group, file, source) {
  const importsCredentialApi = /from\s+['"]@\/api\/credentials['"]/.test(source)
  const brokerCredentials =
    (file === 'src/api/credentials.js' && hasAll(source, '/api/credentials/list', '/api/credentials/create')) ||
    (file === 'src/api/broker.js' && hasAll(source, '/api/ibkr/connect', '/api/alpaca/connect')) ||
    under(file, 'src/views/broker-accounts/') ||
    under(file, 'src/components/ExchangeAccountModal/', 'src/components/RenameCredentialModal/') ||
    importsCredentialApi
  const liveStrategyDeploy =
    (file === 'src/api/strategy.js' && hasAll(source, 'export function startStrategy', 'export function stopStrategy')) ||
    (file === 'src/api/user.js' && hasAll(source, 'export function adminToggleStrategy', '/api/users/system-strategies/toggle')) ||
    (source.includes("from '@/api/user'") && source.includes('adminToggleStrategy')) ||
    (file === 'src/views/strategy-center/index.vue' && hasAll(source, 'startStrategy', 'stopStrategy', "from '@/api/strategy'")) ||
    (file === 'src/views/strategy-center/components/LiveOperationsTable.vue' && hasAll(source, "$emit('start'", "$emit('stop'", 'runtime_health')) ||
    (file === 'src/views/strategy-center/components/LiveStrategyEditor.vue' && hasAll(source, 'createStrategy', "from '@/api/strategy'")) ||
    (file === 'src/views/executor-strategies/index.vue' && hasAll(source, 'createExecutorStrategy', "from '@/api/strategy'"))
  const agentTradingScope =
    (file === 'src/api/agent.js' && hasAll(source, '/api/agent/v1/admin/tokens', '/api/agent/v1/me/tokens')) ||
    (file === 'src/views/agent-tokens/index.vue' && hasAll(source, '<a-checkbox value="T">', 'paper_only', 'live-eligible')) ||
    (file === 'src/views/profile/components/ProfileAgentTokens.vue' && hasAll(source, '<a-checkbox value="T">', 'paper_only', 'ack_live_trading_risk'))
  const billingCredits =
    (file === 'src/api/billing.js' && source.includes('/api/billing/')) ||
    (file === 'src/api/user.js' && /\/api\/users\/[^'"\s]*credits[^'"\s]*/i.test(source)) ||
    (file === 'src/views/billing/index.vue' && source.includes("from '@/api/billing'")) ||
    (file === 'src/config/router.config.js' && hasAll(source, "path: '/billing'", "import('@/views/billing')")) ||
    source.includes("from '@/api/billing'") ||
    (source.includes("from '@/api/user'") && /\b(?:getMyCreditsLog|setUserCredits|getUserCreditsLog)\b/.test(source)) ||
    (under(file, 'src/views/profile/', 'src/views/user-manage/') && /\b(?:creditsLog|creditsModal|formatCredits)\b/.test(source)) ||
    (under(file, 'src/views/ai-analysis/') && /profile-credits|tab:\s*['"]credits['"]/.test(source))
  const paidHiddenMarketplace =
    (under(file, 'src/views/indicator-community/') && [
        'pricing_type',
        'code_hidden',
        '/api/community/my-purchases',
        '/purchase',
        'purchase_price'
      ].some((contract) => source.includes(contract))) ||
    (file === 'src/api/strategy.js' && hasAll(source, 'publishScriptSource', 'pricingType', 'codeHidden')) ||
    (under(file, 'src/views/indicator-ide/') && hasAll(source, 'publishToCommunity', 'pricingType', 'codeHidden')) ||
    (source.includes("from '@/api/strategy'") && hasAll(source, 'publishScriptSource', 'pricingType', 'codeHidden'))
  const rules = {
    broker_credentials: () => brokerCredentials,
    live_orders: () => file === 'src/api/quick-trade.js' || file === 'src/components/QuickTradePanel/QuickTradePanel.vue',
    trading_worker: () => file === 'src/views/executor-strategies/index.vue',
    live_strategy_deploy: () => liveStrategyDeploy,
    agent_trading_scope: () => agentTradingScope,
    grid_copy_trading: () => file === 'src/api/strategy.js' && source.includes('/api/strategies/grid-resting-orders'),
    billing_credits: () => billingCredits,
    paid_hidden_marketplace: () => paidHiddenMarketplace,
    mobile: () => under(file, 'src/mobile/')
  }
  return rules[group]()
}

function groupedHits (files, sources, groups, matcher) {
  return Object.fromEntries(groups.map((group) => [
    group,
    files.filter((file) => matcher(group, file, sources.get(file)))
  ]))
}

export function buildInventory (repositoryRoot = process.cwd()) {
  const root = path.resolve(repositoryRoot)
  const inspectedFiles = trackedScopeFiles(root)
  const sources = new Map(inspectedFiles.map((file) => [file, readFileSync(path.join(root, file), 'utf8')]))
  return {
    sourceBaselines: { ...SOURCE_BASELINES },
    inspectedFiles,
    preservedHits: groupedHits(inspectedFiles, sources, PRESERVED_GROUPS, preservedMatch),
    forbiddenHits: groupedHits(inspectedFiles, sources, FORBIDDEN_GROUPS, forbiddenMatch)
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.stdout.write(`${JSON.stringify(buildInventory(), null, 2)}\n`)
}
