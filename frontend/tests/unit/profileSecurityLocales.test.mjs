import assert from 'node:assert/strict'
import test from 'node:test'

import messages from '../../src/locales/lang/profile-security.js'

const supportedLocales = [
  'ar-SA',
  'de-DE',
  'en-US',
  'fr-FR',
  'ja-JP',
  'ko-KR',
  'ru-RU',
  'th-TH',
  'vi-VN',
  'zh-CN',
  'zh-TW'
]

test('profile security messages cover every supported locale', () => {
  const requiredKeys = Object.keys(messages['en-US']).sort()

  for (const locale of supportedLocales) {
    assert.ok(messages[locale], `Missing locale: ${locale}`)
    assert.deepEqual(Object.keys(messages[locale]).sort(), requiredKeys, `Incomplete locale: ${locale}`)

    for (const key of requiredKeys) {
      assert.equal(typeof messages[locale][key], 'string', `Invalid value: ${locale}.${key}`)
      assert.notEqual(messages[locale][key].trim(), '', `Empty value: ${locale}.${key}`)
      assert.notEqual(messages[locale][key], key, `Untranslated key: ${locale}.${key}`)
    }
  }
})
