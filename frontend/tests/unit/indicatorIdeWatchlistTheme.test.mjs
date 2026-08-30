import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const componentPath = fileURLToPath(
  new URL('../../src/views/indicator-ide/index.vue', import.meta.url)
)
const source = fs.readFileSync(componentPath, 'utf8')

test('add-symbol source selects use a dark dropdown class', () => {
  const matches = source.match(/ide-add-source-dropdown--dark/g) || []
  assert.ok(matches.length >= 3)
  assert.match(source, /\.ide-add-source-dropdown--dark\s*\{[\s\S]*?background:\s*#1f1f1f/)
})

test('selected add-symbol result has an explicit dark-theme override', () => {
  assert.match(
    source,
    /\.ide-modal-wrap--dark\s*\{[\s\S]*?\.ant-list-item\.add-item-active[\s\S]*?background:[^;]+!important/
  )
})
