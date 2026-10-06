import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import test from 'node:test'
const source = readFileSync(new URL('../../src/views/mock-portfolio/portfolioHistory.js',import.meta.url),'utf8')
const helper = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
test('timeframes filter calendar days and preserve missing NAV', () => {
  const rows=[{day:'2026-09-01',nav:'100'},{day:'2026-10-01',nav:null},{day:'2026-10-05',nav:'110'}]
  assert.equal(helper.filterHistory(rows,'1w','2026-10-06').length,2)
  assert.equal(helper.navChartOptions(rows).series[0].connectNulls,false)
  assert.equal(helper.navChartOptions(rows).series[0].data[1],null)
})
