import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
const source=readFileSync(new URL('../../src/views/mock-portfolio/components/PortfolioAlertPreferences.vue',import.meta.url),'utf8')
const context={component:null,ReportPdfReader:{},getAlertPreferences:()=>{},saveAlertPreferences:()=>{},getStrategyNotifications:()=>{},markBookNotificationRead:()=>{}}
vm.runInNewContext(source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'').replace('export default','component ='),context)
test('alerts are opt-in and previous book response is ignored',async()=>{
  let release
  context.getAlertPreferences=id=>id==='a'?new Promise(resolve=>{release=resolve}):Promise.resolve({data:{enabled:false,concentrationPct:50}})
  context.getStrategyNotifications=()=>Promise.resolve({data:{items:[]}})
  const state={...context.component.data(),bookId:'a',$t:key=>key};Object.assign(state,context.component.methods)
  assert.equal(state.form.enabled,false)
  const old=state.load();state.bookId='b';await state.load();release({data:{enabled:true,concentrationPct:10}});await old
  assert.equal(state.form.enabled,false)
})
