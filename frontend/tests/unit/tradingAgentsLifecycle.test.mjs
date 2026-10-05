import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { comparablePreviousReport } from '../../src/utils/researchDecisionBrief.js'

// Execute the real component methods with controlled network/timers. Rendered
// accordion/mobile behavior is also covered by browser acceptance.
function panel (api = {}) {
  const source = readFileSync(new URL('../../src/components/TradingAgents/DeepAnalysisPanel.vue', import.meta.url), 'utf8')
  const script = source.split('<script>')[1].split('</script>')[0]
    .replace(/import[\s\S]*?from ['"][^'"]+['"]/g, '')
    .replace('export default', 'globalThis.component =')
  const context = { ReportPdfReader: {}, HoseResearchEvidence: {}, ResearchDecisionBrief: {}, ...api, window: { clearInterval () {}, setInterval () { return 1 } } }
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

test('decision brief always reads the complete report artifact even when logs come first', async () => {
  const requested = []
  const { instance } = panel({ getTradingAgentsArtifact: async (run, artifact) => { requested.push(artifact); return '## V. Portfolio Manager Decision\n**Rating**: HOLD' } })
  instance.run = { run_id: 'run-1', status: 'succeeded', artifacts: [{ artifact_name: 'events.json' }, { artifact_name: 'complete_report.md' }] }
  await instance.loadReport(instance.run)
  assert.deepEqual(requested, ['complete_report.md'])
})

test('prior private comparison selects the matching earlier period and ignores responses after switching runs', async () => {
  let resolve
  const requested = []
  const { instance } = panel({ comparablePreviousReport, getTradingAgentsArtifact: (run, artifact) => {
    requested.push([run, artifact])
    return new Promise(done => { resolve = done })
  } })
  instance.run = { run_id: 'current', status: 'succeeded' }
  instance.briefReport = { market: 'VNStock', symbol: 'FPT', effectiveDate: '2026-10-05', locale: 'vi-VN', reportKind: 'deep' }
  const prior = { source: 'ACCOUNT_PRIVATE_REPORT', market: 'VNStock', symbol: 'FPT', language: 'vi-VN', status: 'succeeded' }
  instance.historyReports = [
    { ...prior, run_id: 'future', analysis_date: '2026-10-12' },
    { ...prior, run_id: 'other-locale', analysis_date: '2026-10-04', language: 'en-US' },
    { ...prior, run_id: 'prior', analysis_date: '2026-09-28' },
    { ...prior, run_id: 'old', analysis_date: '2026-09-21' }
  ]
  const pending = instance.loadPreviousReport(instance.run)
  assert.deepEqual(requested, [['prior', 'complete_report.md']])
  instance.historyRequestId++
  instance.run = { run_id: 'another', status: 'succeeded' }
  instance.previousReport = { body: 'new context' }
  resolve('old response')
  await pending
  assert.equal(instance.previousReport.body, 'new context')
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

test('failed runs expose only the recovery actions approved by the API policy', () => {
  const { instance, definition } = panel()
  instance.run = {
    run_id: 'run-1',
    status: 'failed',
    failure_code: 'runner_failed',
    recovery: { retryable: true, checkpointable: true }
  }
  assert.equal(definition.computed.isResumable.call(instance), true)
  assert.equal(definition.computed.isCheckpointable.call(instance), true)
  assert.equal(definition.computed.recoveryDescription.call(instance), 'tradingAgents.runnerFailed')

  instance.run = {
    ...instance.run,
    failure_code: 'service_rejected',
    recovery: { retryable: false, checkpointable: false }
  }
  assert.equal(definition.computed.isResumable.call(instance), false)
  assert.equal(definition.computed.isCheckpointable.call(instance), false)
  assert.equal(definition.computed.recoveryDescription.call(instance), 'tradingAgents.serviceRejected')
})
