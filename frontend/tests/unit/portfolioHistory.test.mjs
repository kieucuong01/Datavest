import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
const source = readFileSync(new URL('../../src/views/mock-portfolio/portfolioHistory.js',import.meta.url),'utf8')
const helper = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
test('timeframes filter calendar days and preserve missing NAV', () => {
  const rows=[{day:'2026-09-01',nav:'100'},{day:'2026-10-01',nav:null},{day:'2026-10-05',nav:'110'}]
  assert.equal(helper.filterHistory(rows,'1w','2026-10-06').length,2)
  assert.equal(helper.navChartOptions(rows).series[0].connectNulls,false)
  assert.equal(helper.navChartOptions(rows).series[0].data[1],null)
})
test('benchmark charts keep missing performance as a gap instead of zero', () => {
  const option=helper.benchmarkChartOptions([{day:'2026-10-01',benchmark:'100',portfolio:'100'},{day:'2026-10-02',benchmark:'110',portfolio:null}])
  assert.equal(option.series[1].data[1],null)
  assert.equal(option.series[1].connectNulls,false)
})
test('late benchmark response cannot replace a newer selected key', async () => {
  const componentSource = readFileSync(new URL('../../src/views/mock-portfolio/components/PortfolioNavHistory.vue',import.meta.url),'utf8')
  const context={ component:null,echarts:{},vietnamDay:helper.vietnamDay,filterHistory:helper.filterHistory,navChartOptions:helper.navChartOptions }
  vm.runInNewContext(componentSource.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','component ='),context)
  let release
  context.bookBenchmark = (id,args) => args.key === 'VNINDEX' ? new Promise(resolve=>{release=resolve}) : Promise.resolve({data:{benchmarkKey:'VN30',revision:2,points:[]}})
  const state={...context.component.data(),bookId:'a',revision:2,benchmarkKey:'VNINDEX',visiblePoints:[],$t:k=>k,$nextTick:()=>{}}
  Object.assign(state,context.component.methods)
  const first=state.loadBenchmark();state.benchmarkKey='VN30';await state.loadBenchmark();release({data:{benchmarkKey:'VNINDEX',revision:2,points:[]}});await first
  assert.equal(state.comparison.benchmarkKey,'VN30')
})
