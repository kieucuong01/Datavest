import assert from 'node:assert/strict'
import test from 'node:test'

import { applyAccountDeepReports, applyPublicDeepReports, applySharedResearchStates, buildAccountOpinionRows, buildSharedOpinionRows, buildWatchlistOpinionRows } from '../../src/views/smart-insights/watchlistOpinions.js'
import { extractPortfolioManagerDecisionSummary } from '../../src/utils/tradingAgentsReport.js'

test('prefers the authenticated account deep report over the shared public snapshot', () => {
  const rows = applySharedResearchStates(
    buildAccountOpinionRows(
      [{ market: 'Crypto', symbol: 'SOL/USDT', name: 'Solana' }],
      []
    ),
    [{
      assetKey: 'crypto:SOL/USDT',
      reportKind: 'deep',
      status: 'complete',
      scope: 'public_common',
      report: {
        source: 'PUBLIC_RESEARCH_REPORT',
        effectiveDate: '2026-09-14',
        summary: 'Báo cáo public ngày 14/9'
      }
    }]
  )

  const row = applyAccountDeepReports(rows, [{
    assetKey: 'crypto:SOL/USDT',
    report: {
      source: 'ACCOUNT_PRIVATE_REPORT',
      effectiveDate: '2026-09-16',
      summary: 'Báo cáo riêng ngày 16/9'
    }
  }]).find(item => item.displaySymbol === 'SOL')

  assert.equal(row.deepState.report.source, 'ACCOUNT_PRIVATE_REPORT')
  assert.equal(row.deepState.report.effectiveDate, '2026-09-16')
  assert.equal(row.deepState.report.summary, 'Báo cáo riêng ngày 16/9')
})

test('uses BTC, SOL, LINK and XAU as the guest default assets', () => {
  const rows = buildSharedOpinionRows([], [], null)

  assert.deepEqual(rows.map(row => row.displaySymbol), ['BTC', 'SOL', 'LINK', 'XAU'])
  assert.deepEqual(rows.map(row => row.publicAssetKey), [
    'crypto:BTC/USDT',
    'crypto:SOL/USDT',
    'crypto:LINK/USDT',
    'forex:XAUUSD'
  ])
  assert.equal(rows.some(row => row.displaySymbol === 'VNINDEX'), false)
})

test('renders only watchlist assets in watchlist order', () => {
  const rows = buildWatchlistOpinionRows(
    [
      { market: 'Crypto', symbol: 'ETH/USDT', name: 'Ethereum' },
      { market: 'VNStock', symbol: 'FPT', name: 'FPT' }
    ],
    [
      { market: 'crypto', symbol: 'BTC', report: { id: 1, decision: 'BUY' } },
      { market: 'crypto', symbol: 'ETH', report: { id: 2, decision: 'HOLD' } },
      { market: 'vn', symbol: 'FPT', report: { id: 3, decision: 'BUY' } }
    ]
  )
  assert.deepEqual(rows.map(row => row.symbol), ['ETH/USDT', 'FPT'])
  assert.equal(rows[0].report.decision, 'HOLD')
  assert.equal(rows[1].report.decision, 'BUY')
})

test('shows the shared guest assets first and appends account watchlist assets', () => {
  const rows = buildAccountOpinionRows(
    [
      { market: 'Crypto', symbol: 'ETH/USDT', name: 'Ethereum' },
      { market: 'Crypto', symbol: 'BTC/USDT', name: 'Bitcoin from watchlist' }
    ],
    [
      { market: 'crypto', symbol: 'ETH', report: { id: 2, decision: 'HOLD' } },
      { market: 'crypto', symbol: 'BTC', report: { id: 3, decision: 'BUY' } }
    ]
  )

  assert.deepEqual(rows.map(row => row.displaySymbol), ['BTC', 'SOL', 'LINK', 'XAU', 'ETH'])
  assert.equal(rows[0].watchlistItem.name, 'Bitcoin from watchlist')
  assert.equal(rows[0].report.id, 3)
  assert.equal(rows[4].watchlistItem.name, 'Ethereum')
})

test('keeps a watchlist row when analysis is unavailable', () => {
  const [row] = buildWatchlistOpinionRows(
    [{ market: 'Forex', symbol: 'XAUUSD', name: 'Gold' }],
    []
  )
  assert.equal(row.analysisStatus, 'UNAVAILABLE')
  assert.equal(row.report, null)
})

test('maps the latest shared public opinion into a read-only report for guests', () => {
  const [row] = buildWatchlistOpinionRows(
    [{ market: 'Crypto', symbol: 'BTC/USDT', name: 'Bitcoin' }],
    [{
      id: 'public-opinion-1',
      market: 'crypto',
      symbol: 'BTC',
      stance: 'NEUTRAL',
      score: 0,
      confidence: 70,
      rationale: {
        status: 'EVIDENCE_ONLY',
        metrics: ['crypto.price.usd'],
        warning: 'No directional model has been validated for this evidence bundle.'
      },
      explanation: null,
      dataClass: 'LIVE'
    }],
    '2026-09-12T07:00:00+00:00'
  )

  assert.equal(row.shared, true)
  assert.equal(row.report.source, 'PUBLIC_COMMON_SNAPSHOT')
  assert.equal(row.report.createdAt, '2026-09-12T07:00:00+00:00')
  assert.equal(row.report.decision, 'HOLD')
  assert.equal(row.report.confidence, 70)
  assert.match(row.report.summary, /No directional model/u)
})

test('does not replace an account report with the shared snapshot adapter', () => {
  const [row] = buildWatchlistOpinionRows(
    [{ market: 'Crypto', symbol: 'BTC/USDT', name: 'Bitcoin' }],
    [{
      market: 'crypto',
      symbol: 'BTC',
      stance: 'BUY',
      confidence: 85,
      report: { id: 'account-report-1', decision: 'SELL', summary: 'Private report' }
    }],
    '2026-09-12T07:00:00+00:00'
  )

  assert.equal(row.shared, false)
  assert.equal(row.report.id, 'account-report-1')
  assert.equal(row.report.decision, 'SELL')
})

test('keeps missing shared numeric fields unavailable instead of turning them into zero', () => {
  const [row] = buildWatchlistOpinionRows(
    [{ market: 'Crypto', symbol: 'BTC/USDT', name: 'Bitcoin' }],
    [{ market: 'crypto', symbol: 'BTC', stance: 'NEUTRAL', score: null, confidence: null, dataClass: 'LIVE' }],
    '2026-09-12'
  )

  assert.equal(row.report.score, null)
  assert.equal(row.report.confidence, null)
})

test('builds guest rows from the latest shared snapshot without a personal watchlist', () => {
  const [row] = buildSharedOpinionRows(
    [],
    [{
      id: 'public-btc-opinion',
      market: 'crypto',
      symbol: 'BTC',
      stance: 'BUY',
      score: 72,
      confidence: 81,
      explanation: 'Shared BTC snapshot',
      dataClass: 'LIVE'
    }],
    '2026-09-13T07:00:00+00:00'
  )

  assert.equal(row.displaySymbol, 'BTC')
  assert.equal(row.shared, true)
  assert.equal(row.report.source, 'PUBLIC_COMMON_SNAPSHOT')
  assert.equal(row.report.decision, 'BUY')
})

test('attaches the latest tenant-free TradingAgents report for the fixed guest asset set', () => {
  const rows = applyPublicDeepReports(buildSharedOpinionRows([], [], null), [
    {
      assetKey: 'crypto:BTC/USDT',
      reportKind: 'deep',
      effectiveDate: '2026-09-13',
      generatedAt: '2026-09-13T00:15:00Z',
      summary: 'BTC public daily report',
      decision: 'BUY',
      confidence: 79,
      sections: [{ title: 'Luận điểm', items: ['Public evidence'] }]
    }
  ])

  assert.deepEqual(rows.map(row => row.displaySymbol), ['BTC', 'SOL', 'LINK', 'XAU'])
  assert.equal(rows[0].publicCommon, true)
  assert.equal(rows[0].deepState.report.source, 'PUBLIC_RESEARCH_REPORT')
  assert.equal(rows[0].deepState.report.summary, 'BTC public daily report')
  assert.deepEqual(rows[0].deepState.report.reasons, ['Public evidence'])
  assert.equal(rows[1].deepState, undefined)
})

test('keeps a readable preview and creation time when a latest deep report has no separate summary', () => {
  const [row] = applyPublicDeepReports(buildSharedOpinionRows([], [], null), [{
    assetKey: 'crypto:BTC/USDT',
    reportKind: 'deep',
    effectiveDate: '2026-09-14',
    generatedAt: '2026-09-14T01:12:00Z',
    title: 'Báo cáo chuyên sâu BTC',
    body: '# Báo cáo chuyên sâu BTC\n\nKết luận danh mục và các điều kiện cần theo dõi.',
    sections: []
  }])

  assert.equal(row.deepState.report.title, 'Báo cáo chuyên sâu BTC')
  assert.equal(row.deepState.report.createdAt, '2026-09-14T01:12:00Z')
  assert.match(row.deepState.report.summary, /Kết luận danh mục/u)
})

test('keeps the complete public report body needed for the portfolio decision', () => {
  const longPreamble = `# Báo cáo chuyên sâu BTC\n\n${'Dữ liệu nền đã xác thực. '.repeat(160)}`
  const [row] = applyPublicDeepReports(buildSharedOpinionRows([], [], null), [{
    assetKey: 'crypto:BTC/USDT',
    reportKind: 'deep',
    effectiveDate: '2026-09-14',
    body: `${longPreamble}\n\n## V. Portfolio Manager Decision\n\n**Rating**: Hold\n\n**Time Horizon**: 1–4 tuần\n\n### Executive Summary\n\n**Core Strategy**: Giữ vị thế lõi BTC, không mua đuổi.\n\n**Stop-loss Discipline**: Hạ tỷ trọng nếu thủng vùng hỗ trợ.`,
    sections: []
  }])

  const decision = extractPortfolioManagerDecisionSummary(row.deepState.report.body)

  assert.equal(decision.rating, 'Hold')
  assert.equal(decision.timeHorizon, '1–4 tuần')
  assert.deepEqual(decision.actions, [
    'Core Strategy: Giữ vị thế lõi BTC, không mua đuổi.',
    'Stop-loss Discipline: Hạ tỷ trọng nếu thủng vùng hỗ trợ.'
  ])
})

test('never uses the raw Generated metadata line as a report preview', () => {
  const [row] = applyPublicDeepReports(buildSharedOpinionRows([], [], null), [{
    assetKey: 'crypto:BTC/USDT',
    reportKind: 'deep',
    effectiveDate: '2026-09-14',
    generatedAt: '2026-09-14T01:12:00Z',
    summary: 'Generated: 2026-09-14 08:06:19',
    body: '# Trading Analysis Report: BTC-USD\n\nGenerated: 2026-09-14 08:06:19\n\n## V. Portfolio Manager Decision\n\n**Rating**: Hold',
    sections: []
  }])

  assert.doesNotMatch(row.deepState.report.summary, /^Generated:/u)
})

test('keeps an account monitor separate from the shared public TradingAgents report', () => {
  const rows = applyPublicDeepReports(
    buildAccountOpinionRows(
      [{ market: 'Crypto', symbol: 'BTC/USDT', name: 'Bitcoin' }],
      [{ market: 'crypto', symbol: 'BTC', report: { id: 'account-btc', decision: 'SELL' } }]
    ),
    [{
      assetKey: 'crypto:BTC/USDT',
      reportKind: 'deep',
      effectiveDate: '2026-09-13',
      summary: 'Public BTC daily report',
      decision: 'BUY',
      sections: []
    }]
  )

  assert.equal(rows[0].report.id, 'account-btc')
  assert.equal(rows[0].report.decision, 'SELL')
  assert.equal(rows[0].deepState.report.source, 'PUBLIC_RESEARCH_REPORT')
})
