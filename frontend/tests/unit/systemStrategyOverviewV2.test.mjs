import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = process.cwd()
const apiSource = fs.readFileSync(path.join(root, 'src', 'api', 'user.js'), 'utf8')

test('retired system live-strategy administration stays absent', () => {
  assert.equal(fs.existsSync(path.join(root, 'src', 'views', 'user-manage', 'index.vue')), false)
  assert.doesNotMatch(apiSource, /system-strategies|admin-orders|set-vip/)
  assert.doesNotMatch(apiSource, /adminToggleStrategy|manualConfirmOrder/)
})
