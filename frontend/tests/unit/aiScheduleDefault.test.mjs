import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const page = fs.readFileSync(new URL('../../src/views/ai-analysis/index.vue', import.meta.url), 'utf8')

test('explains that the 07:00 Vietnam daily analysis is system-managed and personal tasks are additional', () => {
  assert.match(page, /aiAssetAnalysis\.systemDaily\.title/u)
  assert.match(page, /aiAssetAnalysis\.systemDaily\.description/u)
})
