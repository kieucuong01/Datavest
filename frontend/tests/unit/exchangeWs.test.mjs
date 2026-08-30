import assert from 'node:assert/strict'
import test from 'node:test'

import { parseGateSpotBar } from '../../src/utils/exchangeWs.js'


test('Gate spot candles use base volume instead of quote turnover', () => {
  const bar = parseGateSpotBar({
    channel: 'spot.candlesticks',
    event: 'update',
    result: {
      t: '1784505600',
      o: '64726.5',
      h: '65662.2',
      l: '63733.8',
      c: '65514.6',
      v: '495134000',
      a: '7557.6131',
      n: '1d_BTC_USDT',
      w: false
    }
  })

  assert.equal(bar.volume, 7557.6131)
  assert.notEqual(bar.volume, 495134000)
  assert.equal(bar.isClosed, false)
})


test('Gate spot candles read the explicit window-close flag', () => {
  const bar = parseGateSpotBar({
    channel: 'spot.candlesticks',
    event: 'update',
    result: {
      t: '1784505600',
      o: '1',
      h: '2',
      l: '1',
      c: '2',
      v: '20',
      a: '10',
      n: '1m_BTC_USDT',
      w: true
    }
  })

  assert.equal(bar.isClosed, true)
})


test('Gate spot candles fail safe when base volume is absent', () => {
  const bar = parseGateSpotBar({
    channel: 'spot.candlesticks',
    event: 'update',
    result: {
      t: '1784505600',
      o: '1',
      h: '2',
      l: '1',
      c: '2',
      v: '500000000',
      n: '1m_BTC_USDT'
    }
  })

  assert.equal(bar.volume, 0)
  assert.equal(bar.isClosed, false)
})
