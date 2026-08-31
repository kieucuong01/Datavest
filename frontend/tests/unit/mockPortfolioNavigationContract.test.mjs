import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const routerSource = fs.readFileSync(new URL('../../src/config/router.config.js', import.meta.url), 'utf8')
const layoutSource = fs.readFileSync(new URL('../../src/layouts/BasicLayout.vue', import.meta.url), 'utf8')

test('Mock Portfolio is visible as a direct header item after Quant Lab', () => {
  const portfolioRoute = routerSource.match(/\{\s*path: '\/portfolio',[\s\S]*?\n      \},/u)

  assert.ok(portfolioRoute, 'the /portfolio route must remain available')
  assert.match(portfolioRoute[0], /component: \(\) => import\('@\/views\/mock-portfolio'\)/u)
  assert.doesNotMatch(portfolioRoute[0], /hidden: true/u)

  const quantGroup = layoutSource.match(/name: 'MenuGroupQuantLab',[\s\S]*?singleAsItem: false/u)
  assert.ok(quantGroup, 'Quant Lab group must remain in the primary navigation')
  assert.match(quantGroup[0], /paths: \['\/portfolio-optimizer', '\/strategy-ide', '\/backtest-center'\]/u)
  assert.match(layoutSource, /return groupedRoutes\.concat\(leftovers\)/u)
})
