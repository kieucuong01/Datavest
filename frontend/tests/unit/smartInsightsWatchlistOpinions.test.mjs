import assert from 'node:assert/strict'
import test from 'node:test'

import { applyPublicQuickReports, buildAccountOpinionRows, buildSharedOpinionRows, buildWatchlistOpinionRows } from '../../src/views/smart-insights/watchlistOpinions.js'

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

test('prioritizes the latest tenant-free quick report for the fixed guest asset set', () => {
  const rows = applyPublicQuickReports(buildSharedOpinionRows([], [], null), [
    {
      assetKey: 'crypto:BTC/USDT',
      reportKind: 'quick',
      effectiveDate: '2026-09-13',
      generatedAt: '2026-09-13T00:15:00Z',
      summary: 'BTC public daily report',
      decision: 'BUY',
      confidence: 79,
      sections: [{ title: 'Luận điểm', items: ['Public evidence'] }]
    }
  ])

  assert.deepEqual(rows.map(row => row.displaySymbol), ['BTC', 'SOL', 'LINK', 'XAU'])
  assert.equal(rows[0].publicResearch, true)
  assert.equal(rows[0].report.source, 'PUBLIC_RESEARCH_REPORT')
  assert.equal(rows[0].report.summary, 'BTC public daily report')
  assert.deepEqual(rows[0].report.reasons, ['Public evidence'])
  assert.equal(rows[1].report, null)
})

test('does not replace an account-owned report with the shared public quick report', () => {
  const rows = applyPublicQuickReports(
    buildAccountOpinionRows(
      [{ market: 'Crypto', symbol: 'BTC/USDT', name: 'Bitcoin' }],
      [{ market: 'crypto', symbol: 'BTC', report: { id: 'account-btc', decision: 'SELL' } }]
    ),
    [{
      assetKey: 'crypto:BTC/USDT',
      reportKind: 'quick',
      effectiveDate: '2026-09-13',
      summary: 'Public BTC daily report',
      decision: 'BUY',
      sections: []
    }]
  )

  assert.equal(rows[0].report.id, 'account-btc')
  assert.equal(rows[0].report.decision, 'SELL')
  assert.equal(rows[0].publicResearch, undefined)
})
