import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const selectLangSource = fs.readFileSync(
  new URL('../../src/components/SelectLang/index.jsx', import.meta.url),
  'utf8'
)
const localesSource = fs.readFileSync(
  new URL('../../src/locales/index.js', import.meta.url),
  'utf8'
)
const appHtml = fs.readFileSync(new URL('../../index.html', import.meta.url), 'utf8')
const publicHtml = fs.readFileSync(new URL('../../public/index.html', import.meta.url), 'utf8')

test('language picker exposes only English and Vietnamese', () => {
  const localesBlock = selectLangSource.match(/const locales = \[([\s\S]*?)\]/)?.[1] || ''
  const locales = [...localesBlock.matchAll(/'([^']+)'/g)].map(match => match[1])

  assert.deepEqual(locales, ['en-US', 'vi-VN'])
})

test('runtime bundles only the Vietnamese lazy locale beside built-in English', () => {
  const loadersBlock = localesSource.match(/const localeLoaders = \{([\s\S]*?)\n\}/)?.[1] || ''
  const loaders = [...loadersBlock.matchAll(/'([^']+)'\s*:/g)].map(match => match[1])

  assert.deepEqual(loaders, ['vi-VN'])
})

test('static HTML metadata does not advertise a retired locale', () => {
  assert.match(appHtml, /<html lang="en">/)
  assert.match(publicHtml, /<html lang="en">/)
})
