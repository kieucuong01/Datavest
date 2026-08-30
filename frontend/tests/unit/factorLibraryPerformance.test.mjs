import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const factorLibraryPath = fileURLToPath(
  new URL('../../src/views/strategy-ide/FactorLibraryModal.vue', import.meta.url)
)
const factorLibrarySource = fs.readFileSync(factorLibraryPath, 'utf8')

test('factor library renders a virtual window instead of the full catalog', () => {
  assert.match(factorLibrarySource, /v-for="factor in virtualFactors"/)
  assert.match(factorLibrarySource, /virtualFactors \(\) \{[\s\S]*?this\.filteredFactors\.slice/)
  assert.doesNotMatch(factorLibrarySource, /v-for="factor in filteredFactors"/)
})

test('factor catalog metadata is reused without a duplicate detail request', () => {
  assert.doesNotMatch(factorLibrarySource, /getFactorDetail/)
  assert.match(
    factorLibrarySource,
    /selectFactor \(factor\) \{[\s\S]*?this\.selectedFactor = factor[\s\S]*?this\.resetParameters\(factor\)/
  )
})

test('factor catalog preloads during an idle browser period', () => {
  assert.match(factorLibrarySource, /mounted \(\) \{[\s\S]*?this\.schedulePreload\(\)/)
  assert.match(factorLibrarySource, /window\.requestIdleCallback\(preload, \{ timeout: 1200 \}\)/)
})
