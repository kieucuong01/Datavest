import assert from 'node:assert/strict'
import path from 'node:path'
import test from 'node:test'

import {
  isTranslatableText,
  loadCoreLocale
} from '../../scripts/i18n-utils.mjs'

const modules = await Promise.all([
  import('../../src/locales/copilot-overrides.js'),
  import('../../src/locales/lang/profile-security.js'),
  import('../../src/locales/lang/broker-account-workspace.js'),
  import('../../src/locales/lang/strategy-v2.js'),
  import('../../src/locales/lang/strategy-live-risk.js'),
  import('../../src/locales/lang/robot-builder-overrides.js'),
  import('../../src/locales/lang/strategy-trade-records.js'),
  import('../../src/locales/portfolio-optimizer.js'),
  import('../../src/locales/smart-insights.js'),
  import('../../src/locales/product-locale-overrides.js'),
  import('../../src/locales/generated-locale-overrides.js')
])

const localeDir = path.resolve('src/locales/lang')

function runtimeMessages (locale) {
  return Object.assign(
    {},
    loadCoreLocale(localeDir, locale).locale,
    ...modules.map(module => module.default?.[locale] || {})
  )
}

test('Vietnamese runtime dictionary covers every English product key', () => {
  const english = runtimeMessages('en-US')
  const vietnamese = runtimeMessages('vi-VN')
  const missing = Object.keys(english).filter(key => !(key in vietnamese))

  assert.deepEqual(missing, [])
})

test('Vietnamese runtime dictionary never exposes Chinese prose', () => {
  const vietnamese = runtimeMessages('vi-VN')
  const leaked = Object.entries(vietnamese)
    .filter(([, value]) => typeof value === 'string' && /[\u3400-\u9fff]/u.test(value))
    .map(([key]) => key)

  assert.deepEqual(leaked, [])
})

test('critical active-workspace labels do not fall back to English', () => {
  const english = runtimeMessages('en-US')
  const vietnamese = runtimeMessages('vi-VN')
  const criticalKeys = [
    'strategyV2.backtest.gridAccountingTitle',
    'strategyCenter.gridOrders.title',
    'executorStrategies.trigger.grid.description',
    'aiAssetAnalysis.copilot.streamInterrupted',
    'smartInsights.title'
  ]

  for (const key of criticalKeys) {
    assert.equal(typeof vietnamese[key], 'string', `${key} must exist`)
    assert.ok(vietnamese[key].trim(), `${key} must not be empty`)
    if (isTranslatableText(english[key])) {
      assert.notEqual(vietnamese[key], english[key], `${key} must be translated`)
    }
  }
})
