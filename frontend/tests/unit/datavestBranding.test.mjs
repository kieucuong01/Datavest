import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => readFileSync(path.join(root, relative), 'utf8')

test('DataVest is the first-paint and runtime product brand', () => {
  const index = read('index.html')
  const settings = read('src/config/defaultSettings.js')
  const brand = read('src/store/modules/brand.js')

  assert.match(index, /<title>DataVest<\/title>/)
  assert.match(index, /Powered by QuantDinger/)
  assert.match(settings, /title: 'DataVest'/)
  assert.match(brand, /app_name: 'DataVest'/)
  assert.match(brand, /datavest\.brand-config\.v1/)
})

test('the derivative notice preserves QuantDinger attribution', () => {
  const notice = read('NOTICE')

  assert.match(notice, /DataVest/)
  assert.match(notice, /Powered by QuantDinger/)
  assert.match(notice, /6f9ce97fe4730355c39a72610f5dbda3f05d3db7/)
  assert.match(notice, /366ea33c276b5307ce8428da6dcca160532635ea/)
})
