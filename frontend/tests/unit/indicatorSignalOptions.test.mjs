import assert from 'node:assert/strict'
import test from 'node:test'

import { extractIndicatorSignalLabels } from '../../src/utils/indicatorSignalOptions.js'

test('extracts signal labels without exposing visual types', () => {
  const code = `
layers = [{"type": "line", "text": "Support line", "data": []}]
output = {
  "signals": [
    {"type": "buy", "text": "Long Entry", "data": long_entries},
    {"type": "sell", "text": "Long Exit", "data": long_exits},
  ],
  "layers": layers,
}
`

  assert.deepEqual(extractIndicatorSignalLabels(code), ['Long Entry', 'Long Exit'])
})

test('supports assigned lists, append calls, and literal textData', () => {
  const code = `
signals = [
  {"type": "buy", "textData": [None, "Breakout", "Retest"], "data": marks},
]
signals.append({"type": "sell", "text": "Risk Exit", "data": exits})
output = {"signals": signals}
`

  assert.deepEqual(extractIndicatorSignalLabels(code), ['Breakout', 'Retest', 'Risk Exit'])
})

test('does not invent fallback signals when code has no named signals', () => {
  const code = 'output = {"signals": [], "plots": []}'
  assert.deepEqual(extractIndicatorSignalLabels(code), [])
})
