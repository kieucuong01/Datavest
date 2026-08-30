import assert from 'node:assert/strict'
import test from 'node:test'

import { splitIndicatorPlotsByPane } from '../../src/utils/indicatorPlotGrouping.js'


test('mixed indicator plots are split between the candle pane and sub-pane', () => {
  const ema = { name: 'EMA', overlay: true }
  const atr = { name: 'ATR' }
  const rsi = { name: 'RSI', overlay: false }

  const groups = splitIndicatorPlotsByPane([ema, atr, rsi])

  assert.deepEqual(groups.overlayPlots, [ema, atr])
  assert.deepEqual(groups.panePlots, [rsi])
})


test('overlay defaults to the candle pane unless explicitly false', () => {
  const implicitOverlay = { name: 'EMA' }
  const explicitSubPane = { name: 'RSI', overlay: false }

  assert.deepEqual(splitIndicatorPlotsByPane([implicitOverlay]), {
    overlayPlots: [implicitOverlay],
    panePlots: []
  })
  assert.deepEqual(splitIndicatorPlotsByPane([explicitSubPane]), {
    overlayPlots: [],
    panePlots: [explicitSubPane]
  })
})
