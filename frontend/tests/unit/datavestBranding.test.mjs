import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => readFileSync(path.join(root, relative), 'utf8')
const collectRuntimeFiles = directory => readdirSync(path.join(root, directory), { withFileTypes: true }).flatMap(entry => {
  const relative = path.join(directory, entry.name)
  if (entry.isDirectory()) return collectRuntimeFiles(relative)
  return /\.(js|vue)$/u.test(entry.name) ? [relative] : []
})

test('DataVest is the first-paint and runtime product brand', () => {
  const index = read('index.html')
  const settings = read('src/config/defaultSettings.js')
  const brand = read('src/store/modules/brand.js')

  assert.match(index, /<title>DataVest<\/title>/)
  assert.match(index, /Powered by DataVest/)
  assert.match(settings, /title: 'DataVest'/)
  assert.match(brand, /app_name: 'DataVest'/)
  assert.match(brand, /datavest\.brand-config\.v1/)
})

test('runtime product copy does not expose the upstream QuantDinger brand', () => {
  const files = ['index.html', 'public/index.html', ...collectRuntimeFiles('src')]
  const source = files.map(relative => read(relative)).join('\n')
    .replace(/https?:\/\/[^'"\\s)]+/giu, '')
    .replace(/quantdinger\.com/giu, '')
    .replace(/(?:ref=|join\/)QUANTDINGER/giu, '')
    .replace(/['"]quantdinger['"]/giu, '')

  assert.doesNotMatch(source, /QuantDinger/iu)
})

test('the derivative notice declares DataVest branding', () => {
  const notice = read('NOTICE')

  assert.match(notice, /DataVest/)
  assert.match(notice, /distributed product branding is DataVest/)
  assert.match(notice, /6f9ce97fe4730355c39a72610f5dbda3f05d3db7/)
  assert.match(notice, /366ea33c276b5307ce8428da6dcca160532635ea/)
})
