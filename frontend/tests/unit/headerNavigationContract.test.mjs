import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const layoutSource = fs.readFileSync(new URL('../../src/layouts/BasicLayout.vue', import.meta.url), 'utf8')
const layoutStyles = fs.readFileSync(new URL('../../src/layouts/BasicLayout.less', import.meta.url), 'utf8')
const routerSource = fs.readFileSync(new URL('../../src/config/router.config.js', import.meta.url), 'utf8')
const localeSource = fs.readFileSync(new URL('../../src/locales/product-locale-overrides.js', import.meta.url), 'utf8')

test('header exposes Smart Insights, AI Assistant, Chart and one Quant Lab group in order', () => {
  assert.equal((layoutSource.match(/name: 'MenuGroup/g) || []).length, 4)
  assert.match(layoutSource, /paths: \[\s*'\/smart-insights'\s*\][\s\S]+?singleAsItem: true/u)
  assert.match(layoutSource, /paths: \[\s*'\/ai-asset-analysis'\s*\][\s\S]+?singleAsItem: true/u)
  assert.match(layoutSource, /paths: \[\s*'\/indicator-ide'\s*\][\s\S]+?singleAsItem: true/u)
  assert.match(layoutSource, /path: '\/menu-group\/quant-lab'/u)
  assert.match(layoutSource, /paths: \[\s*'\/portfolio-optimizer',\s*'\/strategy-ide',\s*'\/backtest-center'\s*\]/u)
  assert.match(layoutSource, /paths: \[\s*'\/portfolio-optimizer',\s*'\/strategy-ide',\s*'\/backtest-center'\s*\][\s\S]+?singleAsItem: false/u)
  assert.doesNotMatch(layoutSource, /path: '\/menu-group\/(strategy-lab|backtest-center)'/u)
})

test('Quant Lab is the active parent for each research workspace route', () => {
  assert.match(layoutSource, /currentPath\.startsWith\(/u)
  assert.match(layoutSource, /children\.some\(isActive\)/u)
  assert.match(layoutSource, /activeTopMenuKey[\s\S]+?menu-group\/quant-lab/u)
})

test('root navigation opens Smart Insights and the group parent redirects safely', () => {
  assert.match(routerSource, /redirect: '\/smart-insights'/u)
  assert.match(routerSource, /path: '\/menu-group\/quant-lab'/u)
  assert.match(routerSource, /redirect: '\/portfolio-optimizer'/u)
  assert.match(routerSource, /path: '\/portfolio-optimizer'/u)
  assert.match(routerSource, /path: '\/strategy-ide'/u)
  assert.match(routerSource, /path: '\/backtest-center'/u)
})

test('navigation labels are available in both EN and VI locale overrides', () => {
  assert.match(localeSource, /menu\.group\.quantLab/u)
  assert.match(localeSource, /menu\.group\.aiAssistant/u)
  assert.match(localeSource, /menu\.group\.chartIndicator/u)
})

test('Quant Lab submenu preserves the individual workspace labels', () => {
  assert.match(layoutSource, /title: group\.singleAsItem \? group\.title : \(route\.meta && route\.meta\.title\) \|\| group\.title/u)
  assert.match(layoutSource, /paths: \[\s*'\/portfolio-optimizer',\s*'\/strategy-ide',\s*'\/backtest-center'\s*\]/u)
})

test('header navigation controls expose polished active, hover, press and focus states', () => {
  assert.match(layoutStyles, /\.basic-layout-wrapper \.ant-layout-header \.ant-menu-horizontal/u)
  assert.match(layoutStyles, /border-radius:\s*10px/u)
  assert.match(layoutStyles, /transform:\s*translateY\(-1px\)/u)
  assert.match(layoutStyles, /:active/u)
  assert.match(layoutStyles, /:focus-visible/u)
  assert.match(layoutStyles, /box-shadow:/u)
})
