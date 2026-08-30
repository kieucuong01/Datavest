import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = path.resolve(import.meta.dirname, '../..')
const component = fs.readFileSync(path.join(root, 'src/views/ai-skills/index.vue'), 'utf8')
const english = fs.readFileSync(path.join(root, 'src/locales/lang/en-US.js'), 'utf8')
const chinese = fs.readFileSync(path.join(root, 'src/locales/lang/zh-CN.js'), 'utf8')

test('AI Skill Center reads user-facing copy from locale files', () => {
  assert.match(component, /this\.\$t\(`aiSkills\.\$\{key\}`\)/)
  assert.doesNotMatch(component, /title:\s*'AI Skill Center'/)
  assert.doesNotMatch(component, /title:\s*'AI 技能中心'/)
  assert.match(english, /"aiSkills\.title": "AI Skill Center"/)
  assert.match(chinese, /"aiSkills\.title": "AI 技能中心"/)
})

test('AI Skill Center safety copy reflects the current live-order contract', () => {
  assert.match(english, /"aiSkills\.ruleBoundary": "Strategy deployments are created stopped by default\."/)
  assert.match(english, /"aiSkills\.ruleUserControl": "Live quick orders require explicit confirmation/)
})
