import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../../src/views/indicator-guest/index.vue', import.meta.url), 'utf8')

function styleRule (selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/gu, '\\$&')
  const match = source.match(new RegExp(`${escapedSelector} \\{[^}]*\\}`, 'u'))
  assert.ok(match, `style rule for ${selector} must exist`)
  return match[0]
}

test('guest chart shell fills the available height instead of reserving a blank tail', () => {
  const shellRule = styleRule('.guest-chart-shell')
  const chartRule = source.match(/\.guest-chart-shell > :deep\(\.chart-left\),\s*\.guest-chart-shell :deep\(\.chart-wrapper\),\s*\.guest-chart-shell :deep\(\.chart-content-area\)\s*\{[^}]*\}/u)
  assert.ok(chartRule, 'chart root height rule must exist')

  assert.match(shellRule, /display:\s*flex/u)
  assert.match(shellRule, /flex-direction:\s*column/u)
  assert.match(chartRule[0], /height:\s*100%/u)
  assert.match(chartRule[0], /min-height:\s*0/u)
})

test('guest chart exposes a localized full-size control wired to the chart shell', () => {
  assert.match(source, /ref="chartShell"/u)
  assert.match(source, /class="guest-chart-fullscreen-button"/u)
  assert.match(source, /:aria-label="isChartFullscreen \? \$t\('indicatorIde\.exitFullscreen'\) : \$t\('indicatorIde\.fullscreenChart'\)"/u)
  assert.match(source, /@click="toggleChartFullscreen"/u)
  assert.match(source, /requestFullscreen/u)
  assert.match(source, /document\.addEventListener\('fullscreenchange', this\.syncChartFullscreen\)/u)
})
