import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const frontendRoot = fileURLToPath(new URL('../..', import.meta.url))
const routerSource = readFileSync(new URL('../../src/config/router.config.js', import.meta.url), 'utf8')
const noticeSource = readFileSync(new URL('../../src/components/NoticeIcon/NoticeIcon.vue', import.meta.url), 'utf8')

test('portfolio route opens the user-facing mock portfolio', () => {
  assert.match(routerSource, /path: '\/portfolio'[\s\S]*?component: \(\) => import\('@\/views\/mock-portfolio'\)/)
  assert.doesNotMatch(routerSource, /import\('@\/views\/portfolio'\)/)
  assert.match(noticeSource, /goToPortfolio \(\)[\s\S]*?path: '\/portfolio-optimizer'/)
})

test('unreferenced legacy page modules stay removed', () => {
  const removedModules = [
    'src/views/portfolio/index.vue',
    'src/views/dashboard/index.vue',
    'src/api/dashboard.js',
    'src/views/404.vue',
    'src/views/exception/403.vue',
    'src/views/exception/500.vue',
    'src/views/user/RegisterResult.vue'
  ]

  removedModules.forEach(relativePath => {
    assert.equal(existsSync(`${frontendRoot}/${relativePath}`), false, `${relativePath} should not be restored`)
  })
})
