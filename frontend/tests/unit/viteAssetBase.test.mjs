import assert from 'node:assert/strict'
import test from 'node:test'

import viteConfig from '../../vite.config.js'

test('uses root-relative assets so nested SPA routes can load the app bundle', () => {
  const config = viteConfig({ command: 'build', mode: 'production' })

  assert.equal(config.base, '/')
})
