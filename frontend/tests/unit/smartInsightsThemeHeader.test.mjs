import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const smartInsightsPage = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/index.vue'), 'utf8')
const marketPulse = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/MarketPulseSection.vue'), 'utf8')
const pulseChart = readFileSync(path.join(repositoryRoot, 'src/views/smart-insights/components/PulseTrendChart.vue'), 'utf8')
const layout = readFileSync(path.join(repositoryRoot, 'src/layouts/BasicLayout.vue'), 'utf8')
const headerStyles = readFileSync(path.join(repositoryRoot, 'src/layouts/BasicLayout.less'), 'utf8')
const topMenuPath = path.join(repositoryRoot, 'src/layouts/TopMenu.vue')
const topMenu = existsSync(topMenuPath) ? readFileSync(topMenuPath, 'utf8') : ''

test('Smart Insights primary accents resolve from the runtime setting color', () => {
  assert.match(smartInsightsPage, /--blue:\s*var\(--primary-color/u)
  assert.match(smartInsightsPage, /--soft-blue:\s*var\(--primary-color-soft/u)
  assert.match(smartInsightsPage, /var\(--blue(?:-active|-hover)?/u)
  assert.match(marketPulse, /border-color:\s*var\(--primary-color-ring/u)
  assert.match(pulseChart, /primaryColor \(\) \{ return \(this\.\$store && this\.\$store\.state\.app\.color\)/u)
  assert.match(pulseChart, /lineStyle:\s*\{[^}]*color:\s*this\.primaryColor/u)
  assert.match(pulseChart, /primaryColor \(\) \{ this\.scheduleRender\(\) \}/u)
  assert.doesNotMatch(smartInsightsPage, /--blue:\s*#174ca8/u)
  assert.doesNotMatch(pulseChart, /color:\s*'#2b6de0'/u)
})

test('top navigation uses a fixed flex renderer instead of Ant Menu overflow dots', () => {
  assert.equal(existsSync(topMenuPath), true, 'TopMenu component must exist')
    assert.match(layout, /menu-render="topMenuRender"/u)
    assert.match(layout, /props\.layout !== 'topmenu'/u)
  assert.match(layout, /import TopMenu from '\.\/TopMenu'/u)
  assert.match(layout, /TopMenu,/u)
  assert.match(topMenu, /class="datavest-top-menu"/u)
  assert.match(topMenu, /menu-group-quant-lab|children/u)
  assert.doesNotMatch(topMenu, /overflowedIndicator|ant-menu-overflowed-submenu|\.\.\./u)
  assert.doesNotMatch(headerStyles, /ant-menu-overflowed-submenu[\s\S]*display:\s*none/u)
})
