import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const layoutStyles = fs.readFileSync(new URL('../../src/layouts/BasicLayout.less', import.meta.url), 'utf8')
const layoutSource = fs.readFileSync(new URL('../../src/layouts/BasicLayout.vue', import.meta.url), 'utf8')
const rightContentSource = fs.readFileSync(new URL('../../src/components/GlobalHeader/RightContent.vue', import.meta.url), 'utf8')
const smartInsightsSource = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
const opinionsSource = fs.readFileSync(new URL('../../src/views/smart-insights/components/AssetOpinionsSection.vue', import.meta.url), 'utf8')
const flowTerminalSource = fs.readFileSync(new URL('../../src/views/smart-insights/components/FlowTerminal.vue', import.meta.url), 'utf8')

test('compact header keeps one accessible menu trigger, brand, and account action', () => {
  assert.match(layoutSource, /'basic-layout-wrapper--compact': isMobile/u)
  assert.match(layoutStyles, /\.basic-layout-wrapper--compact\s*\{[\s\S]*?& \.ant-pro-global-header-trigger\s*\{\s*display:\s*none !important;/u)
  assert.match(layoutStyles, /\.mobile-header-menu-button\s*\{[\s\S]*?width:\s*44px;[\s\S]*?height:\s*44px;/u)
  assert.match(layoutSource, /v-if="isMobile" class="mobile-header-start"[\s\S]*?class="mobile-header-menu-button"[\s\S]*?:aria-expanded="isDrawerOpen[\s\S]*?class="mobile-header-brand"/u)
  assert.match(layoutStyles, /@media \(max-width: 480px\)[\s\S]*?\.ant-pro-global-header-index-action[\s\S]*?min-width:\s*44px/u)
  assert.match(layoutSource, /:logo="currentLogo"/u)
  assert.match(rightContentSource, /<select-lang v-if="!isMobile"/u)
  assert.match(rightContentSource, /<a-tooltip v-if="!isMobile" :title="\$t\('app\.setting\.tooltip'\)"/u)
  assert.match(rightContentSource, /@media \(max-width: 480px\)[\s\S]*?\.guest-login-button[\s\S]*?width:\s*44px[\s\S]*?font-size:\s*0/u)
})

test('route drawer controls remain reachable above the app bar', () => {
  assert.match(layoutSource, /@media \(max-width: 1200px\)[\s\S]*?\.ant-drawer\.ant-drawer-left\.ant-drawer-open[\s\S]*?z-index:\s*1400 !important;/u)
  assert.match(layoutSource, /\.ant-drawer-header-no-title\s*\{\s*position:\s*relative;\s*z-index:\s*20;/u)
  assert.match(layoutSource, /\.ant-drawer-close\s*\{[\s\S]*?width:\s*44px;\s*height:\s*44px;/u)
  assert.match(layoutSource, /renderMobileDrawerUtilities \(h\)[\s\S]*?class: 'mobile-drawer-utilities'[\s\S]*?class: 'mobile-drawer-language-options'[\s\S]*?class: 'mobile-drawer-settings'/u)
})

test('compact route drawer contains keyboard focus across menu and utilities', () => {
  assert.match(layoutSource, /document\.addEventListener\('keydown', this\.handleMobileDrawerKeydown\)/u)
  assert.match(layoutSource, /document\.removeEventListener\('keydown', this\.handleMobileDrawerKeydown\)/u)
  assert.match(layoutSource, /handleMobileDrawerKeydown \(event\) \{[\s\S]*?event\.key !== 'Tab'[\s\S]*?datavest-mobile-drawer-utilities[\s\S]*?event\.preventDefault\(\)[\s\S]*?\.focus\(\)/u)
  assert.match(layoutSource, /h\('div', \{ class: 'mobile-drawer-menu' \}, \[menu, this\.isDrawerOpen \? this\.renderMobileDrawerUtilities\(h\) : null\]\)/u)
  assert.match(layoutSource, /aria-controls="datavest-mobile-route-drawer"/u)
  assert.match(layoutSource, /scheduleMobileFocusRestore \(\) \{[\s\S]*?\.mobile-header-menu-button'\)\?\.focus\(\)/u)
})

test('asset opinion actions become full-width touch controls on narrow phones', () => {
  assert.match(opinionsSource, /@media \(max-width: 680px\)[\s\S]*?\.opinion-row \.opinion-actions\s*\{[\s\S]*?width:\s*100%/u)
  assert.match(opinionsSource, /@media \(max-width: 680px\)[\s\S]*?\.opinion-row \.opinion-actions \.ant-btn\s*\{[\s\S]*?width:\s*100%/u)
})

test('mobile drawer falls back to the normal route menu instead of rendering undefined', () => {
  assert.match(layoutSource, /:menu-render="topMenuRender"/u)
  assert.match(layoutSource, /topMenuRender \(h, props\) \{[\s\S]*?if \(!props \|\| props\.layout !== 'topmenu' \|\| props\.isMobile\)[\s\S]*?const menu = h\(BaseMenu[\s\S]*?this\.renderMobileDrawerUtilities\(h\)/u)
})

test('mobile media query keeps the route menu collapsed until the user opens it', () => {
  assert.match(layoutSource, /const compactNavigation = Boolean\(val\['screen-xs'\] \|\| val\['screen-sm'\] \|\| val\['screen-md'\]\)/u)
  assert.match(layoutSource, /if \(!this\.isMobile && compactNavigation\) \{[\s\S]*?this\.isMobile = true[\s\S]*?this\.collapsed = true/u)
})

test('mobile route drawer receives a real brand title instead of undefined', () => {
  assert.match(layoutSource, /<pro-layout[\s\S]*?v-bind="proLayoutSettings"[\s\S]*?:title="\(brandConfig && brandConfig\.app_name\) \|\| title \|\| 'DataVest'"/u)
})

test('mobile breakpoint re-applies closed state after ProLayout updates its drawer', () => {
  assert.match(layoutSource, /this\.mobileDrawerCloseTimer = window\.setTimeout\(\(\) => \{[\s\S]*?if \(this\.isMobile\) \{[\s\S]*?this\.collapsed = true[\s\S]*?this\.isDrawerOpen = false[\s\S]*?this\.updateMenuFooterPosition\(\)[\s\S]*?\}, 0\)/u)
})

test('asset opinion rows use a predictable one-column flow on narrow screens', () => {
  assert.match(opinionsSource, /@media \(max-width: 680px\)[\s\S]*?\.opinion-row\s*\{[\s\S]*?display:\s*flex[\s\S]*?flex-direction:\s*column/u)
  assert.match(opinionsSource, /\.decision-brief-created\s*\{[\s\S]*?display:\s*block/u)
})

test('decision brief facts use two columns on narrow screens', () => {
  assert.match(smartInsightsSource, /@media \(max-width: 680px\)[\s\S]*?\.brief-facts\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/u)
})

test('flow asset selector becomes a scrollable single-column list on phones', () => {
  assert.match(flowTerminalSource, /@media \(max-width: 680px\)[\s\S]*?\.asset-rail\s*\{\s*grid-template-columns:\s*1fr/u)
  assert.match(flowTerminalSource, /@media \(max-width: 680px\)[\s\S]*?\.asset-rail\s*\{[\s\S]*?max-height:\s*240px/u)
  assert.match(flowTerminalSource, /@media \(max-width: 680px\)[\s\S]*?\.asset-label\s*\{[\s\S]*?text-overflow:\s*ellipsis/u)
})
