import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
const source = readFileSync(new URL('../../src/views/mock-portfolio/components/PortfolioBookWorkspace.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'component =')
const context = { component: null, LedgerEntryForm: {}, LedgerImport: {}, bookApi: {}, crypto: { randomUUID: () => 'key' } }
vm.runInNewContext(script, context)
test('late book response cannot replace selected book', async () => {
  let resolveOld
  context.bookApi.bookState = id => id === 'a' ? new Promise(resolve => { resolveOld = resolve }) : Promise.resolve({ data: { id: 'b', revision: 2, state: {} } })
  context.bookApi.bookEntries = () => Promise.resolve({ data: { entries: [], total: 0 } })
  const state = { ...context.component.data(), selectedId: 'a', $t: k => k }
  Object.assign(state, context.component.methods)
  const old = state.loadBook()
  state.selectedId = 'b'
  await state.loadBook()
  resolveOld({ data: { id: 'a', revision: 1, state: {} } })
  await old
  assert.equal(state.book.id, 'b')
})
