<template>
  <details class="report-branch">
    <summary>{{ localize(section.title) }}</summary>
    <div class="report-branch-content">
      <div v-for="(block, index) in section.blocks" :key="index">
        <div v-if="block.type === 'callout'" class="report-callout" :class="`report-callout--${block.tone || 'info'}`">
          <span>{{ block.label }}</span><strong>{{ block.value }}</strong>
        </div>
        <ul v-else-if="block.type === 'list'"><li v-for="(item, i) in block.items" :key="i">{{ item }}</li></ul>
        <div v-else-if="block.type === 'table'" class="branch-table-scroll" tabindex="0">
          <table><thead><tr><th v-for="(cell, i) in block.headers" :key="i">{{ cell }}</th></tr></thead>
            <tbody><tr v-for="(row, i) in block.rows" :key="i"><td v-for="(cell, j) in row" :key="j">{{ cell }}</td></tr></tbody>
          </table>
        </div>
        <pre v-else-if="block.type === 'code'">{{ block.text }}</pre>
        <p v-else>{{ block.text }}</p>
      </div>
      <report-branch v-for="(child, index) in section.subsections" :key="index" :section="child" :language="language" />
    </div>
  </details>
</template>

<script>
import { localizeTradingAgentsHeading } from '@/utils/tradingAgentsReport'
export default {
  name: 'ReportBranch',
  props: { section: { type: Object, required: true }, language: { type: String, default: 'en-US' } },
  methods: { localize (text) { return localizeTradingAgentsHeading(text, this.language) } }
}
</script>

<style scoped>
.report-branch { min-width: 0; margin: 10px 0; border-left: 2px solid var(--line, #dbe4ef); color: var(--ink, #1f2d3d); }
summary { padding: 12px; min-height: 44px; cursor: pointer; font-weight: 600; line-height: 1.5; overflow-wrap: anywhere; }
summary:hover, summary:focus-visible { background: var(--soft-blue, #f5f9ff); }
.report-branch-content { padding: 0 12px 4px; min-width: 0; font-size: 13px; line-height: 1.75; overflow-wrap: anywhere; }
p, ul { margin: 10px 0; } ul { padding-left: 20px; }
.report-callout { display: grid; grid-template-columns: minmax(110px, .35fr) minmax(0, .65fr); gap: 10px; align-items: center; margin: 10px 0; padding: 10px 12px; border: 1px solid var(--line, #dbe4ef); border-left: 4px solid #2563eb; border-radius: 8px; background: var(--callout-info-bg, var(--soft-blue, #f5f9ff)); }.report-callout > span { color: var(--muted, #61738b); font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }.report-callout > strong { color: var(--ink, #1f2d3d); font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }.report-callout--positive { border-left-color: #16a34a; background: var(--callout-positive-bg, #f0fdf4); }.report-callout--negative { border-left-color: #dc2626; background: var(--callout-negative-bg, #fff1f2); }.report-callout--hold { border-left-color: #d97706; background: var(--callout-hold-bg, #fffbeb); }
.branch-table-scroll { max-width: 100%; overflow-x: auto; }
table { border-collapse: collapse; min-width: 100%; } th, td { padding: 8px; border: 1px solid var(--line, #dbe4ef); text-align: left; min-width: 100px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; }
@media(max-width: 640px) { .report-branch-content { padding-left: 6px; padding-right: 2px; } summary { padding: 10px 6px; } .report-callout { grid-template-columns: 1fr; gap: 3px; } }
</style>
