import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

// Execute the real component methods with controlled network/timers. Rendered
// accordion/mobile behavior is also covered by browser acceptance.
function panel (api = {}) {
  const source = readFileSync(new URL('../../src/components/TradingAgents/DeepAnalysisPanel.vue', import.meta.url), 'utf8')
  const script = source.split('<script>')[1].split('</script>')[0]
    .replace(/import[\s\S]*?from ['"][^'"]+['"]/g, '')
    .replace('export default', 'globalThis.component =')
  const context = { ReportPdfReader: {}, ...api, window: { clearInterval () {}, setInterval () { return 1 } } }
  vm.runInNewContext(script, context)
  const definition = context.component
  const instance = { ...definition.data(), visible: true, $t: key => key, $emit: () => {}, run: { run_id: 'run-1', status: 'running' } }
  Object.entries(definition.methods).forEach(([name, method]) => { instance[name] = method.bind(instance) })
  return { instance, definition }
}

test('transient poll failure keeps the timer and recovers on the next response', async () => {
  let fail = true
  const { instance } = panel({ getTradingAgentsRun: async () => {
    if (fail) throw new Error('network failure')
    return { data: { run_id: 'run-1', status: 'running' } }
  } })
  instance.pollTimer = 123
  await instance.refreshRun()
  assert.equal(instance.pollError, true)
  assert.equal(instance.pollTimer, 123)
  fail = false
  await instance.refreshRun()
  assert.equal(instance.pollError, false)
})

test('only one status request is in flight and obsolete generation cannot overwrite a reopened run', async () => {
  let resolve, calls = 0
  const { instance } = panel({ getTradingAgentsRun: () => { calls++; return new Promise(done => { resolve = done }) } })
  const pending = instance.refreshRun()
  await instance.refreshRun()
  assert.equal(calls, 1)
  instance.stopPolling()
  instance.run = { run_id: 'run-1', status: 'queued' }
  resolve({ data: { run_id: 'run-1', status: 'succeeded' } })
  await pending
  assert.equal(instance.run.status, 'queued')
})

test('missing and failed report artifacts have a retryable state, not an infinite spinner', async () => {
  let fail = true
  const { instance } = panel({ getTradingAgentsArtifact: async () => {
    if (fail) throw new Error('unavailable')
    return '# Report'
  } })
  await instance.loadReport(instance.run)
  assert.equal(instance.reportError, true)
  instance.run.artifacts = [{ artifact_name: 'complete_report.md' }]
  await instance.loadReport(instance.run)
  assert.equal(instance.reportError, true)
  fail = false
  await instance.loadReport(instance.run)
  assert.equal(instance.reportError, false)
  assert.equal(instance.reportContent, '# Report')
})

test('late cancel response cannot mark another asset run cancelled', async () => {
  let resolve
  const { instance } = panel({ cancelTradingAgentsRun: () => new Promise(done => { resolve = done }) })
  const pending = instance.cancel()
  instance.historyRequestId++
  instance.run = { run_id: 'run-2', status: 'running' }
  resolve({})
  await pending
  assert.equal(instance.run.status, 'running')
})

test('report library loads completed history without automatically creating a daily run', async () => {
  const calls = []
  const { instance } = panel({ getTradingAgentsRuns: async params => {
    calls.push(params)
    return { data: {
      runs: [{ run_id: 'old-report', analysis_date: '2026-09-08', status: 'succeeded' }],
      today_run: null
    } }
  } })
  instance.run = null
  instance.isSupported = true
  instance.normalizedTarget = { market: 'Crypto', symbol: 'BTC/USDT' }

  await instance.loadReportHistory()

  assert.equal(JSON.stringify(calls), JSON.stringify([{ market: 'Crypto', symbol: 'BTC/USDT', scope: 'history', limit: 100 }]))
  assert.equal(instance.historyReports[0].run_id, 'old-report')
  assert.equal(instance.todayRun, null)
})
