import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const pagePath = path.join(repositoryRoot, 'src/views/smart-insights/index.vue')
const opinionsPath = path.join(repositoryRoot, 'src/views/smart-insights/components/AssetOpinionsSection.vue')
test('Asset Opinions keeps AI Assistant monitor data outside Smart Insights', () => {
  const page = readFileSync(pagePath, 'utf8')
  const opinions = readFileSync(opinionsPath, 'utf8')

  assert.doesNotMatch(page, /getMonitors/u)
  assert.doesNotMatch(page, /scheduledAnalysis/u)
  assert.match(page, /<a-modal[\s\S]*?:visible="analysisModalVisible"[\s\S]*?centered[\s\S]*?:footer="null"[\s\S]*?@cancel="closeAssetAnalysis"/u)
  assert.doesNotMatch(page, /:visible="analysisDrawerVisible"/u)
  assert.match(page, /openAssetAnalysis/u)
  assert.match(page, /analysisMode: 'deep'/u)
  assert.match(page, /<report-pdf-reader/u)
  assert.doesNotMatch(opinions, /open-analysis/u)
  assert.doesNotMatch(opinions, /@click="openFirstEvidence\(row\)"/u)
})

test('Asset Opinions provides only the TradingAgents research action', () => {
  const opinions = readFileSync(opinionsPath, 'utf8')

  assert.match(opinions, /smartInsights\.refresh/u)
  assert.doesNotMatch(opinions, /quantScore/u)
  assert.doesNotMatch(opinions, /hasValidatedEvidence/u)
  assert.match(opinions, /class="deep-analysis-action"[^>]*@click="\$emit\('open-deep-analysis', row\)"/u)
  assert.doesNotMatch(opinions, /quick-analysis-action/u)
  assert.doesNotMatch(opinions, /create-analysis/u)
  assert.match(opinions, /\.opinion-row > \* \{ min-width: 0; \}/u)
  assert.match(opinions, /grid-template-columns: minmax\(112px, \.55fr\) minmax\(0, 4fr\)/u)
})
