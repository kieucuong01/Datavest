import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

const modalRoot = new URL('../../src/components/ExchangeAccountModal/', import.meta.url)
const routerSource = readFileSync(new URL('../../src/config/router.config.js', import.meta.url), 'utf8')

test('retired exchange environment helper stays absent', () => {
  assert.equal(existsSync(new URL('environmentOptions.js', modalRoot)), false)
})

test('retired exchange account modal stays absent', () => {
  assert.equal(existsSync(new URL('ExchangeAccountModal.vue', modalRoot)), false)
})

test('router does not restore broker account navigation', () => {
  assert.doesNotMatch(routerSource, /broker-accounts/)
})

test('router does not restore exchange account modal imports', () => {
  assert.doesNotMatch(routerSource, /ExchangeAccountModal/)
})
