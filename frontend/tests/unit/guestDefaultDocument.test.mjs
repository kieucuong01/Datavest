import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const testDirectory = resolve(fileURLToPath(new URL('.', import.meta.url)))
const documentHtml = readFileSync(resolve(testDirectory, '../../index.html'), 'utf8')

test('serves Vietnamese light-mode defaults before the guest app mounts', () => {
  assert.match(documentHtml, /<html lang="vi">/)
  assert.match(documentHtml, /color-scheme:\s*light;/)
  assert.match(documentHtml, /Đang tải không gian làm việc/)
})
