import test from 'node:test'
import assert from 'node:assert/strict'

import {
  filterAndSortStrategies,
  normalizeTimestampMilliseconds,
  strategyExchangeId,
  strategyCapital,
  strategyExecutionMode,
  strategyLeverage,
  strategyLastActivityTimestamp,
  strategyQuoteCurrency,
  strategyRuntimeSummary,
  strategySymbol,
  summarizeStrategyPerformance
} from '../../src/utils/strategyRuntime.js'
import {
  normalizeStrategyLogLevel,
  STRATEGY_LOG_FILTERS,
  strategyLogLevelKey
} from '../../src/utils/strategyLogs.js'
import strategyLiveRiskMessages from '../../src/locales/lang/strategy-live-risk.js'

const rows = [
  {
    id: 1,
    strategy_name: 'Signal BTC',
    status: 'stopped',
    execution_mode: 'signal',
    initial_capital: 1000,
    total_pnl: -10,
    updated_at: '2026-07-10T10:00:00Z',
    trading_config: { symbol: 'BTC/USDT', timeframe: '5m' }
  },
  {
    id: 2,
    strategy_name: 'Live ETH Momentum',
    status: 'running',
    initial_capital: 2000,
    total_pnl: 25,
    trading_config: {
      symbol: 'ETH/USDT',
      execution_mode: 'live',
      last_execution_time: 1783677600
    }
  },
  {
    id: 3,
    strategy_name: 'Live SOL Rotation',
    status: 'running',
    execution_mode: 'live',
    initial_capital: 500,
    total_pnl: 5,
    trading_config: JSON.stringify({ symbol: 'SOL/USDT', last_signal_time: '2026-07-10T09:00:00Z' })
  }
]

test('normalizes strategy runtime fields', () => {
  assert.equal(strategyExecutionMode(rows[1]), 'live')
  assert.equal(strategySymbol(rows[2]), 'SOL/USDT')
  assert.equal(strategyLastActivityTimestamp(rows[1]), 1783677600000)
})

test('resolves the live exchange from supported strategy payload shapes', () => {
  assert.equal(strategyExchangeId({ exchange_config: { exchange_id: 'OKX' } }), 'okx')
  assert.equal(strategyExchangeId({ exchange_config: '{"exchangeId":"Bybit"}' }), 'bybit')
  assert.equal(strategyExchangeId({ trading_config: { exchange_id: 'binance' } }), 'binance')
  assert.equal(strategyExchangeId({ exchange_id: 'alpaca' }), 'alpaca')
  assert.equal(strategyExchangeId({}), '')
})

test('normalizes Unix seconds and milliseconds for runtime charts', () => {
  assert.equal(normalizeTimestampMilliseconds(1784434455), 1784434455000)
  assert.equal(normalizeTimestampMilliseconds('1784434455'), 1784434455000)
  assert.equal(normalizeTimestampMilliseconds(1784434455000), 1784434455000)
  assert.equal(normalizeTimestampMilliseconds('2026-07-19T04:14:15Z'), 1784434455000)
})

test('summarizes live operations without excluding strategies that have no trades', () => {
  assert.deepEqual(strategyRuntimeSummary(rows), {
    total: 3,
    running: 2,
    runningLive: 2,
    runningSignal: 0,
    totalPnl: 20,
    totalCapital: 3500
  })
})

test('resolves capital, leverage and quote currency from supported strategy shapes', () => {
  const strategy = {
    initial_capital: 2500,
    leverage: 5,
    trading_config: { symbol: 'Crypto:BTC/USDT@swap', market_type: 'swap' }
  }
  assert.equal(strategyCapital(strategy), 2500)
  assert.equal(strategyLeverage(strategy), 5)
  assert.equal(strategyQuoteCurrency(strategy), 'USDT')
  assert.equal(strategyLeverage({ leverage: 10, trading_config: { market_type: 'spot' } }), 1)
  assert.equal(strategyQuoteCurrency({ trading_config: { symbol: 'USStock:AAPL' } }), 'USD')
})

test('calculates live performance from configured capital and completed trades', () => {
  const summary = summarizeStrategyPerformance({
    strategy: { initial_capital: 1000, total_pnl: 999 },
    curve: [
      { equity: 1020 },
      { equity: 900 },
      { equity: 1010 }
    ],
    trades: [
      { type: 'open_long', profit: null },
      { type: 'add_long', profit: null },
      { type: 'close_long', profit: 20 },
      { type: 'close_short', profit: -10 }
    ]
  })
  assert.equal(summary.capital, 1000)
  assert.equal(summary.latestEquity, 1010)
  assert.equal(summary.netPnl, 10)
  assert.equal(summary.totalReturn, 0.01)
  assert.equal(summary.maxDrawdown, (900 - 1020) / 1020)
  assert.equal(summary.wins, 1)
  assert.equal(summary.completedTrades, 2)
  assert.equal(summary.winRate, 0.5)
})

test('filters and sorts running strategies before stopped strategies', () => {
  const filtered = filterAndSortStrategies(rows, { keyword: 'live', status: 'running', executionMode: 'live' })
  assert.deepEqual(filtered.map(item => item.id), [2, 3])
  assert.deepEqual(filterAndSortStrategies(rows).map(item => item.id), [2, 3, 1])
})

test('keeps warning logs visible and filterable before errors', () => {
  assert.deepEqual(
    STRATEGY_LOG_FILTERS.map(item => item.value),
    ['all', 'trade', 'signal', 'warning', 'error']
  )
  assert.equal(normalizeStrategyLogLevel('warn'), 'warning')
  assert.equal(normalizeStrategyLogLevel('warning'), 'warning')
  assert.equal(strategyLogLevelKey('warn'), 'trading-assistant.logs.level.warning')
})

test('translates strategy log controls in every supported locale', () => {
  const requiredKeys = [
    'trading-assistant.logs.level.warning',
    'trading-assistant.logs.level.error',
    'trading-assistant.logs.autoRefresh',
    'trading-assistant.logs.noLogs'
  ]
  assert.deepEqual(Object.keys(strategyLiveRiskMessages).sort(), [
    'ar-SA', 'de-DE', 'en-US', 'fr-FR', 'ja-JP', 'ko-KR',
    'ru-RU', 'th-TH', 'vi-VN', 'zh-CN', 'zh-TW'
  ])
  Object.values(strategyLiveRiskMessages).forEach(messages => {
    requiredKeys.forEach(key => assert.ok(messages[key], `missing ${key}`))
  })
})
