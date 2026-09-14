import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

function reader (fetchPdf, fetchPublicPdf = fetchPdf, fetchSummaryPdf = fetchPdf, fetchPublicSummaryPdf = fetchPublicPdf) {
  const source = readFileSync(new URL('../../src/components/TradingAgents/ReportPdfReader.vue', import.meta.url), 'utf8')
  const script = source.split('<script>')[1].split('</script>')[0]
    .replace(/import[^\n]+/g, '').replace('export default', 'globalThis.component =')
  const revoked = []
  const context = { Blob, getTradingAgentsReportPdf: fetchPdf, getTradingAgentsSummaryPdf: fetchSummaryPdf, getPublicResearchReportPdf: fetchPublicPdf, getPublicResearchReportSummaryPdf: fetchPublicSummaryPdf, URL: { createObjectURL: () => 'blob:pdf', revokeObjectURL: url => revoked.push(url) } }
  vm.runInNewContext(script, context)
  const instance = { ...context.component.data(), runId: 'a', active: true }
  for (const [name, method] of Object.entries(context.component.methods)) instance[name] = method.bind(instance)
  return { instance, revoked }
}

test('PDF reader discards a late response after changing asset or closing', async () => {
  let resolvePending
  const { instance } = reader(() => new Promise(resolve => { resolvePending = resolve }))
  const loading = instance.loadPdf()
  instance.reset()
  resolvePending(new Blob(['%PDF-1.4']))
  await loading
  assert.equal(instance.pdfUrl, '')
  assert.equal(instance.loading, false)
})

test('PDF reader loads the private summary endpoint when summary view is selected', async () => {
  const calls = []
  const { instance } = reader(
    async () => { throw new Error('full endpoint must not be called') },
    undefined,
    async runId => { calls.push(runId); return new Blob(['%PDF-1.4 summary']) }
  )
  instance.variant = 'summary'
  await instance.loadPdf()
  assert.deepEqual(calls, ['a'])
  assert.equal(instance.pdfUrl, 'blob:pdf')
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

test('PDF reader uses the anonymous public report endpoint for guest deep analysis', async () => {
  const calls = []
  const { instance } = reader(
    async () => { throw new Error('private endpoint must not be called') },
    async assetKey => { calls.push(assetKey); return new Blob(['%PDF-1.4']) }
  )
  instance.runId = ''
  instance.publicAssetKey = 'crypto:BTC/USDT'
  await instance.loadPdf()
  assert.deepEqual(calls, ['crypto:BTC/USDT'])
  assert.equal(instance.pdfUrl, 'blob:pdf')
})

test('PDF reader uses the anonymous public summary endpoint when a guest selects the summary', async () => {
  const calls = []
  const { instance } = reader(
    async () => { throw new Error('private endpoint must not be called') },
    async () => { throw new Error('public full endpoint must not be called') },
    undefined,
    async assetKey => { calls.push(assetKey); return new Blob(['%PDF-1.4 summary']) }
  )
  instance.runId = ''
  instance.publicAssetKey = 'crypto:BTC/USDT'
  instance.variant = 'summary'
  await instance.loadPdf()
  assert.deepEqual(calls, ['crypto:BTC/USDT'])
  assert.equal(instance.pdfUrl, 'blob:pdf')
})

test('PDF reader appends a cache-busting revision when the modal opens again', async () => {
  const calls = []
  const { instance } = reader(async (runId, revision) => {
    calls.push([runId, revision])
    return new Blob(['%PDF-1.4'])
  })
  instance.pdfRevision = 1
  await instance.loadPdf()
  instance.reset()
  instance.pdfRevision = 2
  await instance.loadPdf()
  assert.deepEqual(calls, [['a', 1], ['a', 2]])
})
