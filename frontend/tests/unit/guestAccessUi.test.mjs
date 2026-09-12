import assert from 'node:assert/strict'
import test from 'node:test'

import {
  hasAccessToken,
  loginTarget,
  normalizeAccessToken,
  resolvePostLoginPath
} from '../../src/utils/guestAccess.js'


test('guest access token normalization accepts legacy wrappers but rejects objects', () => {
  assert.equal(normalizeAccessToken(' jwt '), 'jwt')
  assert.equal(normalizeAccessToken({ token: 'wrapped' }), 'wrapped')
  assert.equal(normalizeAccessToken({ value: 'value-token' }), 'value-token')
  assert.equal(normalizeAccessToken({ token: { nested: true } }), null)
  assert.equal(hasAccessToken(null), false)
  assert.equal(hasAccessToken('jwt'), true)
})


test('login target preserves the complete protected destination', () => {
  assert.deepEqual(loginTarget('/strategy-ide?tab=script'), {
    path: '/user/login',
    query: { redirect: '/strategy-ide?tab=script' }
  })
  assert.deepEqual(loginTarget(''), { path: '/user/login' })
})


test('post-login redirect stays local and falls back to Smart Insights', () => {
  assert.equal(resolvePostLoginPath('/strategy-ide?tab=script'), '/strategy-ide?tab=script')
  assert.equal(resolvePostLoginPath('https://attacker.example'), '/smart-insights')
  assert.equal(resolvePostLoginPath('//attacker.example'), '/smart-insights')
  assert.equal(resolvePostLoginPath(''), '/smart-insights')
})
