import assert from 'node:assert/strict'
import test from 'node:test'

import { resolveInitialPreferences } from '../../src/utils/guestPreferences.js'

const applicationDefaults = {
  theme: 'realdark',
  language: 'en-US'
}

test('uses light Vietnamese defaults for a guest without saved preferences', () => {
  const preferences = resolveInitialPreferences({
    token: null,
    savedTheme: null,
    savedLanguage: null,
    ...applicationDefaults
  })

  assert.deepEqual(preferences, {
    theme: 'light',
    language: 'vi-VN'
  })
})

test('migrates unversioned guest dark English preferences to the product defaults', () => {
  const preferences = resolveInitialPreferences({
    token: null,
    savedTheme: 'realdark',
    savedLanguage: 'en-US',
    guestPreferenceVersion: null,
    ...applicationDefaults
  })

  assert.deepEqual(preferences, {
    theme: 'light',
    language: 'vi-VN'
  })
})

test('keeps an explicit guest theme and language choice', () => {
  const preferences = resolveInitialPreferences({
    token: null,
    savedTheme: 'dark',
    savedLanguage: 'en-US',
    guestPreferenceVersion: '1',
    ...applicationDefaults
  })

  assert.deepEqual(preferences, {
    theme: 'dark',
    language: 'en-US'
  })
})

test('keeps existing application defaults for a signed-in user without preferences', () => {
  const preferences = resolveInitialPreferences({
    token: 'authenticated-session',
    savedTheme: null,
    savedLanguage: null,
    ...applicationDefaults
  })

  assert.deepEqual(preferences, applicationDefaults)
})
