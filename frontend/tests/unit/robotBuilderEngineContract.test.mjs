import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const builderPath = fileURLToPath(
  new URL('../../src/views/executor-strategies/index.vue', import.meta.url)
)
const routerSource = readFileSync(new URL('../../src/config/router.config.js', import.meta.url), 'utf8')
const strategyIdeSource = readFileSync(new URL('../../src/views/strategy-ide/index.vue', import.meta.url), 'utf8')

test('retired executor strategy view stays absent', () => {
  assert.equal(existsSync(builderPath), false)
})

test('router does not restore executor strategy navigation', () => {
  assert.doesNotMatch(routerSource, /executor-strategies/)
})

test('strategy IDE does not restore executor strategy imports', () => {
  assert.doesNotMatch(strategyIdeSource, /@\/views\/executor-strategies/)
})

test('strategy IDE does not restore embedded executor workbench markup', () => {
  assert.doesNotMatch(strategyIdeSource, /executor-workbench/)
})

test('strategy IDE does not restore live executor deployment helpers', () => {
  assert.doesNotMatch(strategyIdeSource, /createExecutorStrategy/)
})
