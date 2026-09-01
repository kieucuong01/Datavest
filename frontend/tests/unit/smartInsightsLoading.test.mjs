import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const coordinatorPath = path.join(repositoryRoot, 'src/views/smart-insights/loadingCoordinator.js')

test('Smart Insights starts every section concurrently and settles loading independently', async () => {
  assert.equal(existsSync(coordinatorPath), true, 'Smart Insights loading coordinator must exist')
  const { runSectionLoaders } = await import(pathToFileURL(coordinatorPath).href)
  assert.equal(typeof runSectionLoaders, 'function')

  const calls = []
  const loadingEvents = []
  const releases = {}
  const loader = name => () => new Promise((resolve, reject) => {
    calls.push(name)
    releases[name] = { resolve, reject }
  })

  const pending = runSectionLoaders({
    overview: loader('overview'),
    pulse: loader('pulse'),
    calendar: loader('calendar')
  }, (section, active) => loadingEvents.push([section, active]))

  assert.deepEqual(calls, ['overview', 'pulse', 'calendar'])
  assert.deepEqual(loadingEvents, [
    ['overview', true],
    ['pulse', true],
    ['calendar', true]
  ])

  releases.overview.resolve('overview-ready')
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(loadingEvents.at(-1), ['overview', false])
  assert.equal(loadingEvents.some(([section, active]) => section === 'pulse' && active === false), false)

  releases.pulse.reject(new Error('pulse unavailable'))
  releases.calendar.resolve('calendar-ready')
  const results = await pending

  assert.deepEqual(results.map(result => [result.section, result.status]), [
    ['overview', 'fulfilled'],
    ['pulse', 'rejected'],
    ['calendar', 'fulfilled']
  ])
  assert.deepEqual(loadingEvents.slice(-2), [
    ['pulse', false],
    ['calendar', false]
  ])
})
