import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const layoutStyles = fs.readFileSync(new URL('../../src/layouts/BasicLayout.less', import.meta.url), 'utf8')
const layoutSource = fs.readFileSync(new URL('../../src/layouts/BasicLayout.vue', import.meta.url), 'utf8')
const opinionsSource = fs.readFileSync(new URL('../../src/views/smart-insights/components/AssetOpinionsSection.vue', import.meta.url), 'utf8')
const flowTerminalSource = fs.readFileSync(new URL('../../src/views/smart-insights/components/FlowTerminal.vue', import.meta.url), 'utf8')

test('mobile header preserves 44px actions without the desktop refresh control', () => {
  assert.match(layoutStyles, /@media \(max-width: 480px\)[\s\S]*?\.ant-pro-global-header-content\s*\{\s*display:\s*none !important;/u)
  assert.match(layoutStyles, /@media \(max-width: 480px\)[\s\S]*?\.ant-pro-global-header-trigger[\s\S]*?width:\s*48px/u)
  assert.match(layoutStyles, /@media \(max-width: 480px\)[\s\S]*?\.ant-pro-global-header-index-action[\s\S]*?min-width:\s*44px/u)
})

test('asset opinion actions become full-width touch controls on narrow phones', () => {
  assert.match(opinionsSource, /@media \(max-width: 680px\)[\s\S]*?\.opinion-row \.opinion-actions\s*\{[\s\S]*?width:\s*100%/u)
  assert.match(opinionsSource, /@media \(max-width: 680px\)[\s\S]*?\.opinion-row \.opinion-actions \.ant-btn\s*\{[\s\S]*?width:\s*100%/u)
})

test('mobile drawer falls back to the normal route menu instead of rendering undefined', () => {
  assert.match(layoutSource, /topMenuRender \(h, props\) \{[\s\S]*?if \(!props \|\| props\.layout !== 'topmenu' \|\| props\.isMobile\) return false/u)
})

test('mobile media query keeps the route menu collapsed until the user opens it', () => {
  assert.match(layoutSource, /if \(!this\.isMobile && val\['screen-xs'\]\) \{[\s\S]*?this\.isMobile = true[\s\S]*?this\.collapsed = true/u)
})

test('asset opinion rows use a predictable one-column flow on narrow screens', () => {
  assert.match(opinionsSource, /@media \(max-width: 680px\)[\s\S]*?\.opinion-row\s*\{[\s\S]*?display:\s*flex[\s\S]*?flex-direction:\s*column/u)
  assert.match(opinionsSource, /@media \(max-width: 680px\)[\s\S]*?\.report-status\s+small\s*\{[\s\S]*?display:\s*block/u)
})

test('flow asset selector becomes a scrollable single-column list on phones', () => {
  assert.match(flowTerminalSource, /@media \(max-width: 680px\)[\s\S]*?\.asset-rail\s*\{\s*grid-template-columns:\s*1fr/u)
  assert.match(flowTerminalSource, /@media \(max-width: 680px\)[\s\S]*?\.asset-rail\s*\{[\s\S]*?max-height:\s*240px/u)
  assert.match(flowTerminalSource, /@media \(max-width: 680px\)[\s\S]*?\.asset-label\s*\{[\s\S]*?text-overflow:\s*ellipsis/u)
})
