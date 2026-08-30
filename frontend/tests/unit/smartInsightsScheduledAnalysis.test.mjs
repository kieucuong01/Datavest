import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const pagePath = path.join(repositoryRoot, 'src/views/smart-insights/index.vue')
const opinionsPath = path.join(repositoryRoot, 'src/views/smart-insights/components/AssetOpinionsSection.vue')
const helperPath = path.join(repositoryRoot, 'src/views/smart-insights/scheduledAnalysis.js')

test('Asset Opinions opens one centered analysis modal with a close action', () => {
  const page = readFileSync(pagePath, 'utf8')
  const opinions = readFileSync(opinionsPath, 'utf8')

  assert.match(page, /getMonitors/u)
  assert.match(page, /<a-modal[\s\S]*?:visible="analysisModalVisible"[\s\S]*?centered[\s\S]*?:footer="null"[\s\S]*?@cancel="closeAssetAnalysis"/u)
  assert.doesNotMatch(page, /:visible="analysisDrawerVisible"/u)
  assert.match(page, /openAssetAnalysis/u)
  assert.match(page, /noticeMessageHtml/u)
  assert.match(page, /scheduledAnalysis/u)
  assert.match(opinions, /open-analysis/u)
  assert.doesNotMatch(opinions, /@click="openFirstEvidence\(row\)"/u)
})

test('Asset Opinions keeps the 80/20 summary and one useful row action', () => {
  const opinions = readFileSync(opinionsPath, 'utf8')

  assert.match(opinions, /smartInsights\.refresh/u)
  assert.doesNotMatch(opinions, /smartInsights\.refreshAi/u)
  assert.doesNotMatch(opinions, /smartInsights\.weight/u)
  assert.doesNotMatch(opinions, /<a-button size="small" disabled>/u)
  assert.match(opinions, /<a-button size="small" type="primary" icon="search" @click="\$emit\('open-analysis', row\)">/u)
})

test('scheduled analysis index matches the watchlist identity and keeps the latest task', async () => {
  assert.equal(existsSync(helperPath), true, 'scheduled analysis mapper must exist')
  const { buildScheduledAnalysisIndex } = await import(pathToFileURL(helperPath).href)
  const index = buildScheduledAnalysisIndex([
    {
      id: 10,
      config: { market: 'crypto', symbol: 'BTC/USDT' },
      last_run_at: '2026-08-28T08:00:00Z',
      last_result: { success: true, analysis: '<p>old</p>' }
    },
    {
      id: 11,
      config: { market: 'crypto', symbol: 'BTC/USDT' },
      last_run_at: '2026-08-29T08:00:00Z',
      last_result: { success: true, analysis: '<p>latest</p>' }
    }
  ])

  assert.equal(index['crypto:BTC'].id, 11, 'the mapper must expose the canonical key used by watchlist rows')
  assert.equal(index['crypto:BTC/USDT'], undefined)
})
