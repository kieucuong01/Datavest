import assert from 'node:assert/strict'
import test from 'node:test'

import { resolveAiRequestLanguage } from '../../src/utils/aiRequestLanguage.js'

test('AI requests prefer the language saved in Settings when i18n is stale', () => {
  assert.equal(resolveAiRequestLanguage('vi-VN', 'en-US'), 'vi-VN')
  assert.equal(resolveAiRequestLanguage('en-US', 'vi-VN'), 'en-US')
})

test('AI requests retain a supported UI locale when Settings is unavailable', () => {
  assert.equal(resolveAiRequestLanguage('', 'vi-VN'), 'vi-VN')
  assert.equal(resolveAiRequestLanguage(undefined, 'en-US'), 'en-US')
})

test('AI requests fall back to English for an unsupported language value', () => {
  assert.equal(resolveAiRequestLanguage('zh-CN', 'th-TH'), 'en-US')
})
