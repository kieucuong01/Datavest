import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildTradeReviewWindow,
  calculateTradeValueUsd,
  findNearestBarIndex,
  normalizeReviewTimeframe,
  resolveTradeReviewTimeframe
} from '../../src/utils/tradeReview.js'

test('normalizes minute periods without turning them into month periods', () => {
  assert.equal(normalizeReviewTimeframe('1m'), '1m')
  assert.equal(normalizeReviewTimeframe('30M'), '30m')
  assert.equal(normalizeReviewTimeframe('1h'), '1H')
  assert.equal(normalizeReviewTimeframe('1d'), '1D')
})

test('calculates opening USD value from quantity and entry price', () => {
  const value = calculateTradeValueUsd({ quantity: 0.1485, entry_price: 63951.96 })
  assert.ok(Math.abs(value - 9496.86606) < 0.000001)
  assert.equal(calculateTradeValueUsd({ quantity: -2, entry_price: 100 }), 200)
  assert.equal(calculateTradeValueUsd({ value_usd: 350, quantity: 2, entry_price: 100 }), 350)
})

test('builds a bounded historical window around the selected trade', () => {
  const trade = {
    entry_time: '2026-07-18T00:07:00Z',
    exit_time: '2026-07-18T00:28:00Z'
  }
  const result = buildTradeReviewWindow(trade, '1m')

  assert.equal(result.entryTime, Date.parse(trade.entry_time))
  assert.equal(result.exitTime, Date.parse(trade.exit_time))
  assert.ok(result.beforeTime > result.exitTime / 1000)
  assert.ok(result.limit >= 180)
  assert.ok(result.limit <= 1000)
})

test('treats legacy timezone-less backtest times as UTC instants', () => {
  const result = buildTradeReviewWindow({
    entry_time: '2026-07-20 12:00:00',
    exit_time: '2026-07-20 14:00:00'
  }, '1H')

  assert.equal(result.entryTime, Date.parse('2026-07-20T12:00:00Z'))
  assert.equal(result.exitTime, Date.parse('2026-07-20T14:00:00Z'))
})

test('uses the finest timeframe that can include both trade markers', () => {
  const trade = {
    entry_time: '2026-07-03T21:15:00Z',
    exit_time: '2026-07-05T22:32:00Z'
  }

  assert.equal(resolveTradeReviewTimeframe(trade, '1m'), '5m')
  const result = buildTradeReviewWindow(trade, resolveTradeReviewTimeframe(trade, '1m'))
  assert.ok(result.limit <= 1000)
  assert.ok(result.beforeTime > result.exitTime / 1000)
})

test('finds the closest loaded candle for an execution timestamp', () => {
  const rows = [{ timestamp: 1000 }, { timestamp: 2000 }, { timestamp: 3000 }]
  assert.equal(findNearestBarIndex(rows, 2200), 1)
  assert.equal(findNearestBarIndex([], 2200), -1)
})
