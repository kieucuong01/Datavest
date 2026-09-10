import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

function reader (fetchPdf) {
  const source = readFileSync(new URL('../../src/components/TradingAgents/ReportPdfReader.vue', import.meta.url), 'utf8')
  const script = source.split('<script>')[1].split('</script>')[0]
    .replace(/import[^\n]+/g, '').replace('export default', 'globalThis.component =')
  const revoked = []
  const context = { Blob, getTradingAgentsReportPdf: fetchPdf, URL: { createObjectURL: () => 'blob:pdf', revokeObjectURL: url => revoked.push(url) } }
  vm.runInNewContext(script, context)
  const instance = { ...context.component.data(), runId: 'a', active: true }
  for (const [name, method] of Object.entries(context.component.methods)) instance[name] = method.bind(instance)
  return { instance, revoked }
}

test('PDF reader discards a late response after changing asset or closing', async () => {
  let resolve
  const { instance } = reader(() => new Promise(r => { resolve = r }))
  const loading = instance.loadPdf()
  instance.reset()
  resolve(new Blob(['%PDF-1.4']))
  await loading
  assert.equal(instance.pdfUrl, '')
  assert.equal(instance.loading, false)
})

test('PDF reader recovers after failure and releases its URL on close', async () => {
  let attempts = 0
  const { instance, revoked } = reader(async () => {
    if (++attempts === 1) throw new Error('offline')
    return new Blob(['%PDF-1.4'])
  })
  await instance.loadPdf()
  assert.equal(instance.error, true)
  await instance.loadPdf()
  assert.equal(instance.pdfUrl, 'blob:pdf')
  assert.equal(instance.error, false)
  await instance.loadPdf()
  assert.equal(attempts, 2)
  instance.reset()
  assert.deepEqual(revoked, ['blob:pdf'])
})
