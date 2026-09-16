import assert from 'node:assert/strict'
import test from 'node:test'

import { mergeTradingAgentsHistory } from '../../src/components/TradingAgents/tradingAgentsHistory.js'

test('merges account and public reports into one newest-first history with source labels', () => {
  const history = mergeTradingAgentsHistory(
    [{
      run_id: 'private-16',
      market: 'Crypto',
      symbol: 'SOL/USDT',
      analysis_date: '2026-09-16',
      finished_at: '2026-09-16T03:00:00Z',
      status: 'succeeded'
    }],
    [{
      assetKey: 'crypto:SOL/USDT',
      effectiveDate: '2026-09-14',
      generatedAt: '2026-09-14T03:40:15Z'
    }]
  )

  assert.deepEqual(history.map(item => item.run_id), ['private-16', 'public:crypto:SOL/USDT:2026-09-14'])
  assert.equal(history[0].source, 'ACCOUNT_PRIVATE_REPORT')
  assert.equal(history[1].source, 'PUBLIC_RESEARCH_REPORT')
  assert.equal(history[1].public_asset_key, 'crypto:SOL/USDT')
  assert.equal(history[1].analysis_date, '2026-09-14')
})
