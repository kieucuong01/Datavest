import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const pagePath = path.join(repositoryRoot, 'src/views/smart-insights/index.vue')
const opinionsPath = path.join(repositoryRoot, 'src/views/smart-insights/components/AssetOpinionsSection.vue')
test('Asset Opinions only reads date-pinned AI Assistant reports', () => {
  const page = readFileSync(pagePath, 'utf8')
  const opinions = readFileSync(opinionsPath, 'utf8')

  assert.doesNotMatch(page, /getMonitors/u)
  assert.doesNotMatch(page, /scheduledAnalysis/u)
  assert.match(page, /<a-modal[\s\S]*?:visible="analysisModalVisible"[\s\S]*?centered[\s\S]*?:footer="null"[\s\S]*?@cancel="closeAssetAnalysis"/u)
  assert.doesNotMatch(page, /:visible="analysisDrawerVisible"/u)
  assert.match(page, /openAssetAnalysis/u)
  assert.match(page, /selectedOpinionReport/u)
  assert.match(page, /dailyBrief/u)
  assert.match(page, /toggleHeroSpeech/u)
  assert.match(opinions, /open-analysis/u)
  assert.doesNotMatch(opinions, /@click="openFirstEvidence\(row\)"/u)
})

test('Asset Opinions keeps the 80/20 summary and one useful row action', () => {
  const opinions = readFileSync(opinionsPath, 'utf8')

  assert.match(opinions, /smartInsights\.refresh/u)
  assert.match(opinions, /row\.report/u)
  assert.doesNotMatch(opinions, /quantScore/u)
  assert.doesNotMatch(opinions, /hasValidatedEvidence/u)
  assert.match(opinions, /<a-button size="small" type="primary" icon="search" @click="\$emit\('open-analysis', row\)">/u)
})
