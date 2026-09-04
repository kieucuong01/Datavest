<template>
  <section class="flow-terminal" aria-labelledby="flow-terminal-title">
    <header class="flow-terminal-header">
      <div>
        <h3 id="flow-terminal-title">{{ $t('smartInsights.flowTerminalTitle') }}</h3>
        <p>{{ $t('smartInsights.flowTerminalDesc') }}</p>
      </div>
      <a-tag v-if="isCurrent" color="green"><i class="live-dot" />{{ $t('smartInsights.currentData') }}</a-tag>
    </header>

    <div v-if="assetOptions.length" class="flow-terminal-layout">
      <aside class="asset-rail" :aria-label="$t('smartInsights.flowAssets')">
        <h4>{{ $t('smartInsights.flowAssets') }}</h4>
        <button
          v-for="asset in assetOptions"
          :key="asset.symbol"
          type="button"
          :class="{ active: selectedAsset === asset.symbol }"
          @click="selectedAsset = asset.symbol"
        >
          <span class="asset-label"><i :style="{ background: asset.color }" />{{ asset.label }}</span>
          <strong :class="valueClass(assetLatest(asset.symbol))">{{ formatFlow(assetLatest(asset.symbol)) }}</strong>
        </button>
      </aside>

      <div class="flow-main">
        <div class="flow-kpis">
          <article><span>{{ selectedLabel }} · {{ $t('smartInsights.flow24h') }}</span><strong :class="valueClass(latestValue)">{{ formatFlow(latestValue) }}</strong><small>{{ latestDate }}</small></article>
          <article><span>{{ $t('smartInsights.flowNet7d') }}</span><strong :class="valueClass(net7d)">{{ formatFlow(net7d) }}</strong><small>{{ $t('smartInsights.flowAcrossAssets') }}</small></article>
          <article><span>{{ $t('smartInsights.flowNetPeriod') }}</span><strong :class="valueClass(netVisible)">{{ formatFlow(netVisible) }}</strong><small>{{ rangeLabel }}</small></article>
          <article><span>{{ $t('smartInsights.flowPositiveDays') }}</span><strong>{{ positiveDays }} / {{ visibleRows.length }}</strong><small>{{ $t('smartInsights.flowObservedDays') }}</small></article>
        </div>

        <article class="terminal-card">
          <div class="terminal-card-heading">
            <div><h4>{{ selectedLabel }} · {{ $t('smartInsights.flowTitle') }}</h4><small>{{ $t('smartInsights.flowDesc') }}</small></div>
            <div class="terminal-controls">
              <div class="control-group" role="group" :aria-label="$t('smartInsights.flowMode')">
                <button type="button" :class="{ active: mode === 'flow' }" @click="mode = 'flow'">{{ $t('smartInsights.flowModeNet') }}</button>
                <button type="button" :class="{ active: mode === 'cumulative' }" @click="mode = 'cumulative'">{{ $t('smartInsights.flowModeCumulative') }}</button>
              </div>
              <div class="control-group" role="group" :aria-label="$t('smartInsights.flowRange')">
                <button v-for="option in rangeOptions" :key="option" type="button" :class="{ active: range === option }" @click="range = option">{{ option === 'ALL' ? $t('smartInsights.flowRangeAll') : option }}</button>
              </div>
            </div>
          </div>
          <div v-if="!chartRows.length" class="terminal-empty"><a-icon type="bar-chart" />{{ $t('smartInsights.noHistory') }}</div>
          <div v-else ref="chart" class="flow-chart" role="img" :aria-label="$t('smartInsights.flowTitle')" />
        </article>

        <div class="flow-details-grid">
          <article class="terminal-card flow-table-card">
            <div class="terminal-card-heading table-heading"><div><h4>{{ $t('smartInsights.flowTableTitle') }} · {{ selectedLabel }}</h4><small>{{ $t('smartInsights.flowTableDesc') }}</small></div></div>
            <div class="flow-table-scroll">
              <table>
                <thead><tr><th>{{ $t('smartInsights.dateLabel') }}</th><th>{{ $t('smartInsights.flowTotal') }}</th><th v-for="asset in tableAssets" :key="asset.symbol">{{ asset.symbol }}</th></tr></thead>
                <tbody>
                  <tr v-for="row in tableRows" :key="row.date">
                    <th>{{ formatDate(row.date) }}</th><td :class="valueClass(row.total)">{{ formatFlow(row.total) }}</td>
                    <td v-for="asset in tableAssets" :key="asset.symbol" :class="valueClass(row.values[asset.symbol])">{{ formatFlow(row.values[asset.symbol]) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
          <aside class="flow-summary">
            <h4>{{ $t('smartInsights.flowSummary') }}</h4>
            <dl><div><dt>{{ $t('smartInsights.flowNet7d') }}</dt><dd :class="valueClass(net7d)">{{ formatFlow(net7d) }}</dd></div><div><dt>{{ $t('smartInsights.flowNet30d') }}</dt><dd :class="valueClass(net30d)">{{ formatFlow(net30d) }}</dd></div><div><dt>{{ $t('smartInsights.flowNet90d') }}</dt><dd :class="valueClass(net90d)">{{ formatFlow(net90d) }}</dd></div><div><dt>{{ $t('smartInsights.flowLargestIn') }}</dt><dd class="positive">{{ formatFlow(largestIn) }}</dd></div><div><dt>{{ $t('smartInsights.flowLargestOut') }}</dt><dd class="negative">{{ formatFlow(largestOut) }}</dd></div></dl>
          </aside>
        </div>
      </div>
    </div>
    <div v-else class="terminal-empty"><a-icon type="database" />{{ $t('smartInsights.noHistory') }}</div>
  </section>
</template>

<script>
import * as echarts from 'echarts'
import { formatVietnamDate } from '@/utils/vietnamTime'

const ASSET_META = {
  BTC: ['Bitcoin', '#f59e0b'], ETH: ['Ethereum', '#818cf8'], SOL: ['Solana', '#a78bfa'], XRP: ['XRP', '#38bdf8'], HYPE: ['Hyperliquid', '#2563eb'], DOGE: ['Dogecoin', '#ca8a04'], LINK: ['Chainlink', '#3157c8'], AVAX: ['Avalanche', '#ef4444'], HBAR: ['Hedera', '#64748b'], LTC: ['Litecoin', '#3b82f6'], BNB: ['BNB', '#eab308'], DOT: ['Polkadot', '#db2777'], SUI: ['Sui', '#60a5fa']
}
const ASSET_ORDER = Object.keys(ASSET_META)

export default {
  name: 'FlowTerminal',
  props: { flow: { type: Object, default: () => ({}) }, isCurrent: { type: Boolean, default: false } },
  data () { return { selectedAsset: 'TOTAL', mode: 'flow', range: '90D', chart: null, resizeObserver: null, onWindowResize: null } },
  computed: {
    locale () { return this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US' },
    rangeOptions () { return ['7D', '30D', '90D', 'ALL'] },
    rawPoints () {
      return (Array.isArray(this.flow.series) ? this.flow.series : []).map(point => ({ date: String(point && point.effectiveAt || '').slice(0, 10), symbol: String(point && point.symbol || '').toUpperCase(), value: Number(point && point.value) })).filter(point => point.date && ASSET_META[point.symbol] && Number.isFinite(point.value))
    },
    assetOptions () {
      const available = new Set(this.rawPoints.map(point => point.symbol))
      return [{ symbol: 'TOTAL', label: this.$t('smartInsights.flowAllAssets'), color: '#64748b' }, ...ASSET_ORDER.filter(symbol => available.has(symbol)).map(symbol => ({ symbol, label: ASSET_META[symbol][0], color: ASSET_META[symbol][1] }))]
    },
    tableAssets () { return this.assetOptions.filter(asset => asset.symbol !== 'TOTAL') },
    matrixRows () {
      const byDate = new Map()
      for (const point of this.rawPoints) {
        if (!byDate.has(point.date)) byDate.set(point.date, { date: point.date, values: {} })
        byDate.get(point.date).values[point.symbol] = point.value
      }
      return Array.from(byDate.values()).map(row => ({ ...row, total: Object.values(row.values).reduce((sum, value) => sum + value, 0) })).sort((left, right) => left.date.localeCompare(right.date))
    },
    selectedRows () { return this.selectedAsset === 'TOTAL' ? this.matrixRows : this.matrixRows.filter(row => Number.isFinite(row.values[this.selectedAsset])) },
    visibleRows () { const limit = { '7D': 7, '30D': 30, '90D': 90 }[this.range]; return limit ? this.selectedRows.slice(-limit) : this.selectedRows },
    chartRows () {
      let cumulative = 0
      return this.visibleRows.map(row => { const value = this.selectedAsset === 'TOTAL' ? row.total : row.values[this.selectedAsset]; cumulative += value; return { ...row, value: this.mode === 'cumulative' ? cumulative : value } })
    },
    tableRows () { return [...this.visibleRows].reverse() },
    selectedLabel () { return this.selectedAsset === 'TOTAL' ? this.$t('smartInsights.flowAllAssets') : (ASSET_META[this.selectedAsset] || [this.selectedAsset])[0] },
    latestValue () { return this.visibleRows.length ? this.valueOf(this.visibleRows[this.visibleRows.length - 1]) : null },
    latestDate () { return this.visibleRows.length ? this.formatDate(this.visibleRows[this.visibleRows.length - 1].date) : '—' },
    netVisible () { return this.sum(this.visibleRows) },
    net7d () { return this.sum(this.selectedRows.slice(-7)) },
    net30d () { return this.sum(this.selectedRows.slice(-30)) },
    net90d () { return this.sum(this.selectedRows.slice(-90)) },
    positiveDays () { return this.visibleRows.filter(row => this.valueOf(row) > 0).length },
    largestIn () { return this.selectedRows.length ? Math.max(...this.selectedRows.map(row => this.valueOf(row))) : null },
    largestOut () { return this.selectedRows.length ? Math.min(...this.selectedRows.map(row => this.valueOf(row))) : null },
    rangeLabel () { return this.range === 'ALL' ? this.$t('smartInsights.flowRangeAll') : this.range }
  },
  watch: {
    flow: { deep: true, handler () { if (!this.assetOptions.some(asset => asset.symbol === this.selectedAsset)) this.selectedAsset = 'TOTAL'; this.scheduleRender() } },
    selectedAsset () { this.scheduleRender() },
mode () { this.scheduleRender() },
range () { this.scheduleRender() }
  },
  mounted () { this.onWindowResize = () => this.chart && this.chart.resize(); window.addEventListener('resize', this.onWindowResize); this.scheduleRender() },
  beforeDestroy () { window.removeEventListener('resize', this.onWindowResize); if (this.resizeObserver) this.resizeObserver.disconnect(); if (this.chart) this.chart.dispose() },
  methods: {
    valueOf (row) { return this.selectedAsset === 'TOTAL' ? row.total : row.values[this.selectedAsset] },
    sum (rows) { return rows.reduce((sum, row) => sum + this.valueOf(row), 0) },
    assetLatest (symbol) { const row = [...this.matrixRows].reverse().find(item => symbol === 'TOTAL' || Number.isFinite(item.values[symbol])); return row ? (symbol === 'TOTAL' ? row.total : row.values[symbol]) : null },
    scheduleRender () { this.$nextTick(() => this.renderChart()) },
    renderChart () {
      if (!this.chartRows.length || !this.$refs.chart) { if (this.chart) this.chart.clear(); return }
      if (!this.chart) { this.chart = echarts.init(this.$refs.chart); if (typeof ResizeObserver !== 'undefined') { this.resizeObserver = new ResizeObserver(() => this.chart && this.chart.resize()); this.resizeObserver.observe(this.$refs.chart) } }
      const cumulative = this.mode === 'cumulative'
      this.chart.setOption({
        animationDuration: 260,
grid: { left: 8, right: 10, top: 18, bottom: 30, containLabel: true },
        tooltip: { trigger: 'axis', axisPointer: { type: cumulative ? 'line' : 'shadow' }, backgroundColor: '#182235', borderWidth: 0, textStyle: { color: '#f8fafc', fontSize: 12 }, formatter: params => { const row = this.chartRows[params[0].dataIndex]; return `<strong>${this.formatDate(row.date)}</strong><br>${this.selectedLabel}: ${this.formatFlow(row.value)}` } },
        xAxis: { type: 'category', data: this.chartRows.map(row => row.date), boundaryGap: !cumulative, axisTick: { show: false }, axisLine: { lineStyle: { color: '#dbe3ef' } }, axisLabel: { color: '#718096', fontSize: 11, formatter: value => this.formatDateShort(value) } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf1f6' } }, axisLabel: { color: '#718096', fontSize: 11, formatter: value => this.formatCompact(value) } },
        series: [{ type: cumulative ? 'line' : 'bar', smooth: cumulative, showSymbol: false, barMaxWidth: 18, lineStyle: { width: 2.5, color: '#2b6de0' }, areaStyle: cumulative ? { color: 'rgba(43,109,224,.10)' } : undefined, data: this.chartRows.map(row => cumulative ? row.value : { value: row.value, itemStyle: { color: row.value >= 0 ? '#159f72' : '#db5d61', borderRadius: row.value >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3] } }), markLine: cumulative ? undefined : { silent: true, symbol: 'none', lineStyle: { color: '#9aa8ba', type: 'dashed' }, data: [{ yAxis: 0 }] } }]
      }, true)
    },
    valueClass (value) { return Number.isFinite(Number(value)) ? (Number(value) > 0 ? 'positive' : Number(value) < 0 ? 'negative' : 'neutral') : 'neutral' },
    formatFlow (value) { return Number.isFinite(Number(value)) ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 2, signDisplay: 'always' }).format(Number(value)) : '—' },
    formatCompact (value) { return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(Number(value)) },
    formatDate (value) { return formatVietnamDate(`${value}T00:00:00Z`, { locale: this.locale, fallback: value }) },
    formatDateShort (value) { return formatVietnamDate(`${value}T00:00:00Z`, { locale: this.locale, fallback: value, short: true }) }
  }
}
</script>

<style lang="less" scoped>
.flow-terminal { margin-top: 14px; padding: 18px; border: 1px solid var(--line); border-radius: 13px; background: #f7f9fd; }
.flow-terminal-header, .terminal-card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.flow-terminal-header { margin-bottom: 14px; }.flow-terminal h3, .flow-terminal h4 { margin: 0; color: var(--ink); font-weight: 750; }.flow-terminal h3 { font-size: 23px; }.flow-terminal h4 { font-size: 14px; }.flow-terminal p, .terminal-card-heading small, .flow-kpis small { display: block; margin: 4px 0 0; color: var(--muted); font-size: 12px; }.flow-terminal-header .ant-tag { margin: 0; border-radius: 999px; }.live-dot { display: inline-block; width: 6px; height: 6px; margin-right: 5px; border-radius: 50%; background: #18a575; vertical-align: 1px; }
.flow-terminal-layout { display: grid; grid-template-columns: 214px minmax(0, 1fr); gap: 16px; }.asset-rail, .terminal-card, .flow-summary { border: 1px solid var(--line); border-radius: 10px; background: var(--card); }.asset-rail { padding: 12px; }.asset-rail h4 { margin: 3px 0 9px; color: var(--muted); font-size: 11px; font-weight: 700; }.asset-rail button { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 31px; padding: 5px 8px; border: 0; border-radius: 6px; color: var(--ink); background: transparent; font-size: 12px; text-align: left; cursor: pointer; }.asset-rail button:hover, .asset-rail button.active { background: #e8edf6; }.asset-label { display: flex; align-items: center; gap: 7px; }.asset-label i { width: 7px; height: 7px; border-radius: 50%; }.asset-rail strong { font-size: 11px; font-variant-numeric: tabular-nums; }
.flow-main { min-width: 0; }.flow-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }.flow-kpis article { display: grid; gap: 7px; min-height: 92px; padding: 13px; border: 1px solid var(--line); border-radius: 9px; background: var(--card); }.flow-kpis span { color: var(--muted); font-size: 11px; text-transform: uppercase; }.flow-kpis strong { color: var(--ink); font-size: 21px; font-variant-numeric: tabular-nums; }.positive { color: #14944f !important; }.negative { color: #d2263d !important; }.neutral { color: var(--muted) !important; }
.terminal-card { overflow: hidden; }.terminal-card-heading { padding: 13px 15px; border-bottom: 1px solid var(--line); }.terminal-controls, .control-group { display: flex; gap: 4px; }.control-group { padding: 3px; border: 1px solid var(--line); border-radius: 7px; background: var(--page-bg); }.control-group button { min-height: 26px; padding: 3px 8px; border: 0; border-radius: 5px; color: var(--muted); background: transparent; font-size: 11px; cursor: pointer; }.control-group button.active { color: var(--ink); background: var(--card); box-shadow: 0 1px 3px rgba(20,35,60,.12); }.flow-chart { width: 100%; height: 280px; }.terminal-empty { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 180px; color: var(--muted); font-size: 13px; }
.flow-details-grid { display: grid; grid-template-columns: minmax(0, 1fr) 255px; gap: 12px; margin-top: 12px; }.table-heading { padding-bottom: 11px; }.flow-table-scroll { overflow-x: auto; }.flow-table-card table { width: 100%; min-width: 830px; border-collapse: collapse; font-size: 11px; }.flow-table-card th, .flow-table-card td { padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }.flow-table-card th:first-child { text-align: left; background: #f2f5fa; color: var(--muted); font-weight: 600; }.flow-table-card thead th { color: var(--muted); font-size: 10px; text-transform: uppercase; }.flow-summary { padding: 15px; }.flow-summary h4 { padding-bottom: 11px; border-bottom: 1px solid var(--line); }.flow-summary dl { margin: 0; }.flow-summary dl div { display: flex; justify-content: space-between; gap: 10px; padding: 11px 0; border-bottom: 1px solid var(--line); }.flow-summary dt { color: var(--muted); font-size: 12px; }.flow-summary dd { margin: 0; font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }
@media (max-width: 980px) { .flow-terminal-layout { grid-template-columns: 1fr; }.asset-rail { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 3px; }.asset-rail h4 { grid-column: 1 / -1; }.flow-details-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .flow-terminal { padding: 13px; }.flow-terminal-header, .terminal-card-heading { flex-direction: column; }.flow-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }.asset-rail { grid-template-columns: 1fr; max-height: 240px; overflow-y: auto; overscroll-behavior: contain; }.asset-rail button { min-width: 0; min-height: 36px; }.asset-label { min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }.asset-rail strong { flex: 0 0 auto; margin-left: 8px; white-space: nowrap; }.terminal-controls { width: 100%; flex-wrap: wrap; }.flow-chart { height: 235px; } }
</style>
<style lang="less" scoped>
.flow-table-scroll { max-height: 372px; overflow: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.flow-table-card thead th { position: sticky; top: 0; z-index: 1; background: #f7f9fd; }
</style>
