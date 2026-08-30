import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const editorPath = fileURLToPath(
  new URL('../../src/views/strategy-center/components/LiveStrategyEditor.vue', import.meta.url)
)
const routerSource = readFileSync(new URL('../../src/config/router.config.js', import.meta.url), 'utf8')

test('retired live strategy editor stays absent', () => {
  assert.equal(existsSync(editorPath), false)
})

test('router does not restore live strategy editor imports', () => {
  assert.doesNotMatch(routerSource, /LiveStrategyEditor/)
})
