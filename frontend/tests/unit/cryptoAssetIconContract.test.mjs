import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const read = relative => readFileSync(path.join(root, relative), 'utf8')

test('shared crypto asset icon maps common symbols and keeps a deterministic fallback', () => {
  const source = read('src/components/CryptoAssetIcon.vue')

  assert.match(source, /cryptocurrency-color:btc/u)
  assert.match(source, /cryptocurrency-color:eth/u)
  assert.match(source, /cryptocurrency-color:sol/u)
  assert.match(source, /cryptocurrency-color:xrp/u)
  assert.match(source, /cryptocurrency-color:link/u)
  assert.match(source, /separatorIndex/u)
  assert.match(source, /USDT/u)
  assert.match(source, /crypto-asset-icon__fallback/u)
})

test('shared asset icon supports gold and Vietnamese stock logo candidates with image fallback', () => {
  const source = read('src/components/CryptoAssetIcon.vue')

  assert.match(source, /fa6-solid:coins/u)
  assert.match(source, /logos\.hunter\.io/u)
  assert.match(source, /img\.loadlogo\.com\/ticker/u)
  assert.match(source, /handleLogoLoad/u)
  assert.match(source, /handleLogoError/u)
  assert.match(source, /vnstock/u)
})

test('crypto identity is shown in Smart Insights asset opinions', () => {
  const source = read('src/views/smart-insights/components/AssetOpinionsSection.vue')

  assert.match(source, /CryptoAssetIcon/u)
  assert.match(source, /:market="row\.market"/u)
  assert.match(source, /row\.displaySymbol/u)
})

test('crypto identity is shown in AI Assistant selector and watchlist', () => {
  const source = read('src/views/ai-analysis/index.vue')

  assert.match(source, /CryptoAssetIcon/u)
  assert.match(source, /stock\.market/u)
  assert.match(source, /selectedSymbolForAdd\.market/u)
  assert.match(source, /:symbol="stock\.symbol"/u)
  assert.match(source, /:market="stock\.market"/u)
})

test('crypto identity is shown in Mock Portfolio allocation and holdings', () => {
  const source = read('src/views/mock-portfolio/index.vue')

  assert.match(source, /CryptoAssetIcon/u)
  assert.match(source, /item\.market/u)
  assert.match(source, /record\.market/u)
  assert.match(source, /:market="item\.market"/u)
})

test('crypto identity is shown in Quant Portfolio Optimizer instruments and results', () => {
  const source = read('src/views/portfolio-optimizer/index.vue')

  assert.match(source, /CryptoAssetIcon/u)
  assert.match(source, /instrument\.market/u)
  assert.match(source, /item\.symbol/u)
  assert.match(source, /:market=/u)
})
