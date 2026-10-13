import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const source = readFileSync(new URL('../../src/views/ai-analysis/components/CopilotWorkbench.vue', import.meta.url), 'utf8')
const expressions = {
  fallback: source.match(/meta: (data\.intent \?[^\n]+)/)[1],
  stream: source.match(/assistantMsg\.meta = (payload\.intent \?[^\n]+)/)[1]
}

for (const [path, expression] of Object.entries(expressions)) {
  for (const confidence of [undefined, null, NaN, Infinity, '50', 0, 73]) {
    test(`${path} shows only finite numeric confidence: ${String(confidence)}`, () => {
      const response = { intent: 'research', confidence }
      const result = vm.runInNewContext(expression, {
        data: response, payload: response, assistantMsg: { meta: '' }
      })
      const expected = Number.isFinite(confidence) ? `research · ${confidence}%` : 'research'
      assert.equal(result, expected)
    })
  }
}
