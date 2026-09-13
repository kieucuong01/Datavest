import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = relativePath => fs.readFileSync(new URL(relativePath, import.meta.url), 'utf8')

const appSource = read('../../src/App.vue')
const modalSource = read('../../src/components/AuthModal/AuthModal.vue')
const modalBusSource = read('../../src/utils/authModal.js')
const loginSource = read('../../src/views/user/Login.vue')
const headerSource = read('../../src/components/GlobalHeader/RightContent.vue')
const smartInsightsSource = read('../../src/views/smart-insights/index.vue')
const indicatorGuestSource = read('../../src/views/indicator-guest/index.vue')
const permissionSource = read('../../src/permission.js')

test('the app mounts one global authentication modal', () => {
  assert.match(appSource, /AuthModal/u)
  assert.match(appSource, /<auth-modal\s*\/>/u)
  assert.match(modalSource, /<a-modal/u)
  assert.match(modalSource, /:visible="visible"/u)
  assert.match(modalSource, /@cancel="close"/u)
  assert.match(modalSource, /<login/u)
})

test('authentication modal bus carries login or register intent without changing the URL', () => {
  assert.match(modalBusSource, /export function openAuthModal/u)
  assert.match(modalBusSource, /\$emit\(['"]open['"]/u)
  assert.match(modalSource, /initial-tab/u)
  assert.match(modalSource, /redirect/u)
  assert.match(modalSource, /destroy-on-close/u)
})

test('the existing login and registration forms support embedded modal mode', () => {
  assert.match(loginSource, /embedded:\s*\{/u)
  assert.match(loginSource, /initialTab:\s*\{/u)
  assert.match(loginSource, /redirect:\s*\{/u)
  assert.match(loginSource, /auth-embedded/u)
  assert.match(loginSource, /\$emit\(['"]authenticated['"]\)/u)
})

test('guest authentication entry points open the modal instead of navigating to login', () => {
  assert.match(headerSource, /openAuthModal/u)
  assert.doesNotMatch(headerSource, /this\.\$router\.push\(loginTarget/u)
  assert.match(smartInsightsSource, /openAuthModal/u)
  assert.doesNotMatch(smartInsightsSource, /this\.\$router\.push\(loginTarget/u)
  assert.match(indicatorGuestSource, /openAuthModal/u)
  assert.doesNotMatch(indicatorGuestSource, /this\.\$router\.push\(loginTarget/u)
})

test('guest navigation to protected routes opens the modal after the app is mounted', () => {
  assert.match(permissionSource, /isAuthModalReady/u)
  assert.match(permissionSource, /openAuthModal\(\{\s*redirect:\s*to\.fullPath\s*\}\)/u)
  assert.match(permissionSource, /next\(false\)/u)
  assert.match(permissionSource, /query:\s*\{\s*redirect:\s*to\.fullPath\s*\}/u)
})
