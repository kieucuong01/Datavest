import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')

test('asset quick and deep analysis share a wide desktop reading modal', () => {
  assert.match(source, /<a-modal[\s\S]*?:width="1180"[\s\S]*?analysisModalTitle/u)
  assert.match(source, /\.asset-analysis-modal \.ant-modal \{ max-width: calc\(100vw - 24px\); \}/u)
  assert.match(source, /@media \(max-width: 680px\)[\s\S]*?\.asset-analysis-modal \.ant-modal \{ width: calc\(100vw - 16px\) !important/u)
})
