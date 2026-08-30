import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const viewPath = fileURLToPath(new URL('../../src/views/indicator-community/index.vue', import.meta.url))
const source = fs.readFileSync(viewPath, 'utf8')

test('free research library always exposes source before forking', () => {
  assert.match(source, /source_visible/)
  assert.match(source, /detail\.code/)
  assert.match(source, /\/fork`/)
  assert.match(source, /Fork to my workspace/)
})

test('free research library has no purchase or hidden-code flow', () => {
  assert.doesNotMatch(source, /pricing_type|purchase_price|my-purchases|\/purchase|code_hidden/)
  assert.match(source, /Free · source visible/)
})

test('authors and admins can unpublish or review free publications', () => {
  assert.match(source, /\/author\/published/)
  assert.match(source, /\/unpublish`/)
  assert.match(source, /\/admin\/pending-indicators/)
  assert.match(source, /action, note/)
})
