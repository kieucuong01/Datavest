import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const universeLibraryPath = fileURLToPath(
  new URL('../../src/views/strategy-ide/UniverseLibraryModal.vue', import.meta.url)
)
const universeLibrarySource = fs.readFileSync(universeLibraryPath, 'utf8')

test('universe filters keep the detail selection inside the visible catalog', () => {
  assert.match(universeLibrarySource, /scopeFilter \(\) \{[\s\S]*?ensureFilteredSelection\(\)/)
  assert.match(universeLibrarySource, /marketFilter \(\) \{[\s\S]*?ensureFilteredSelection\(\)/)
  assert.match(universeLibrarySource, /this\.filteredUniverses\.find\(item => Number\(item\.id\) === Number\(selectedId\)\)/)
  assert.match(universeLibrarySource, /if \(!preferred\) \{[\s\S]*?this\.selected = null[\s\S]*?this\.members = \[\]/)
})

test('universe member requests are cached and stale responses cannot replace the current selection', () => {
  assert.match(universeLibrarySource, /memberCache: Object\.create\(null\)/)
  assert.match(universeLibrarySource, /if \(!force && this\.memberCache\[cacheKey\]\)/)
  assert.match(universeLibrarySource, /requestId === this\.memberRequestId && this\.selected/)
})

test('universe actions keep readable styles and block an unnamed personal universe', () => {
  assert.match(universeLibrarySource, /class="universe-create-button"/)
  assert.match(universeLibrarySource, /class="universe-apply-button"/)
  assert.match(universeLibrarySource, /:ok-button-props="\{ props: \{ disabled: !canCreateUniverse \} \}"/)
  assert.match(universeLibrarySource, /canCreateUniverse \(\) \{[\s\S]*?createForm\.name/)
})
