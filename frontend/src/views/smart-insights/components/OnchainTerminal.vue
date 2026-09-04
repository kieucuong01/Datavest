<template>
  <section class="onchain-terminal" aria-labelledby="onchain-terminal-title">
    <header class="terminal-header">
      <div>
        <h3 id="onchain-terminal-title">On-chain Terminal</h3>
        <p>{{ isVietnamese ? 'Bốn nhóm dữ liệu blockchain, chỉ hiển thị khi đã có nguồn xác thực.' : 'Four blockchain data groups; values appear only after a verified source import.' }}</p>
      </div>
      <a-tag :color="onchain.status === 'AVAILABLE' ? 'green' : 'orange'">{{ statusLabel(onchain.status) }}</a-tag>
    </header>

    <article v-for="definition in definitions" :key="definition.key" class="onchain-group" :class="`group-${definition.key}`">
      <header class="group-header">
        <div class="group-heading"><span class="group-number">{{ definition.number }}</span><div><h4>{{ definition.label }}</h4><p>{{ definition.description }}</p></div></div>
        <a-tag :color="groupFor(definition.key).status === 'AVAILABLE' ? 'green' : 'default'">{{ statusLabel(groupFor(definition.key).status) }}</a-tag>
      </header>

      <div class="metric-grid">
        <article v-for="spec in definition.metrics" :key="spec.metric" class="metric-card" :class="{ unavailable: !latestFor(spec.metric) }">
          <div class="metric-copy"><small>{{ spec.label }}</small><span>{{ latestFor(spec.metric) ? instrumentLabel(latestFor(spec.metric)) : unavailableText }}</span></div>
          <strong v-if="latestFor(spec.metric)">{{ formatValue(latestFor(spec.metric).value, latestFor(spec.metric).unit) }}</strong>
          <strong v-else>—</strong>
          <small class="metric-status">{{ latestFor(spec.metric) ? formatDate(latestFor(spec.metric).effectiveAt) : unavailableText }}</small>
        </article>
      </div>

      <div v-if="chartEntries(definition.key).length" class="group-chart-grid">
        <article v-for="entry in chartEntries(definition.key)" :key="entry.key" class="chart-shell">
          <header><span>{{ entry.label }}</span><small>{{ entry.symbol || 'ALL' }}</small></header>
          <div :ref="`chart_${entry.key}`" class="onchain-chart" role="img" :aria-label="entry.label" />
        </article>
      </div>
      <div v-else class="source-pending"><a-icon type="database" />{{ unavailableText }} · {{ isVietnamese ? 'Không dùng giá trị minh hoạ hoặc suy diễn.' : 'No placeholder or inferred value is used.' }}</div>
    </article>
  </section>
</template>

<script>
import * as echarts from 'echarts'
import { formatVietnamDate } from '@/utils/vietnamTime'

const DEFINITIONS = [
  {
    key: 'valuation',
number: '01',
label: 'Định giá & lợi nhuận',
description: 'MVRV, NUPL, RHODL, Supply in Profit và SOPR.',
    metrics: [
      { metric: 'crypto.onchain.mvrv', label: 'MVRV' },
      { metric: 'crypto.onchain.nupl', label: 'NUPL' },
      { metric: 'crypto.onchain.rhodl_ratio', label: 'RHODL Ratio' },
      { metric: 'crypto.onchain.supply_in_profit_pct', label: 'Supply in Profit' },
      { metric: 'crypto.onchain.sopr', label: 'SOPR' }
    ]
  },
  {
    key: 'holders',
number: '02',
label: 'Hành vi Holder',
description: 'Nguồn cung LTH/STH, HODL Waves, realized price và cost basis.',
    metrics: [
      { metric: 'crypto.onchain.lth_supply', label: 'LTH Supply' },
      { metric: 'crypto.onchain.sth_supply', label: 'STH Supply' },
      { metric: 'crypto.onchain.hodl_waves', label: 'HODL Waves' },
      { metric: 'crypto.onchain.realized_price', label: 'Realized Price' },
      { metric: 'crypto.onchain.cost_basis', label: 'Cost Basis' }
    ]
  },
  {
    key: 'liquidity',
number: '03',
label: 'Thanh khoản on-chain',
description: 'Dòng vào/ra sàn, dự trữ sàn và nguồn cung stablecoin.',
    metrics: [
      { metric: 'crypto.onchain.exchange_netflow_native', label: 'Exchange Netflow' },
      { metric: 'crypto.onchain.exchange_reserve_native', label: 'Exchange Reserve' },
      { metric: 'crypto.onchain.exchange_inflow_native', label: 'Exchange Inflow' },
      { metric: 'crypto.onchain.exchange_outflow_native', label: 'Exchange Outflow' },
      { metric: 'crypto.stablecoin.supply_usd', label: 'Stablecoin Supply' }
    ]
  },
  {
    key: 'network',
number: '04',
label: 'Sức khoẻ mạng',
description: 'Địa chỉ hoạt động, giao dịch, phí, hash rate, issuance; ETH bổ sung burn/staking/validator queue khi nguồn sẵn sàng.',
    metrics: [
      { metric: 'crypto.onchain.active_addresses', label: 'Active Addresses' },
      { metric: 'crypto.onchain.transaction_count', label: 'Transaction Count' },
      { metric: 'crypto.onchain.total_fees_native', label: 'Total Fees' },
      { metric: 'crypto.mining.hashrate_hs', label: 'Hash Rate' },
      { metric: 'crypto.eth.staking', label: 'ETH Staking' },
      { metric: 'crypto.eth.burn', label: 'ETH Burn' }
    ]
  }
]

export default {
  name: 'OnchainTerminal',
  props: { onchain: { type: Object, default: () => ({}) } },
  data () { return { definitions: DEFINITIONS, chartInstances: {}, resizeObserver: null, onWindowResize: null } },
  computed: {
    isVietnamese () { return this.$i18n && this.$i18n.locale === 'vi-VN' },
    unavailableText () { return this.isVietnamese ? 'Nguồn chưa kết nối' : 'Source not connected' },
    groups () { return Array.isArray(this.onchain.groups) ? this.onchain.groups : [] }
  },
  watch: { onchain: { deep: true, handler () { this.scheduleRender() } } },
  mounted () { this.onWindowResize = () => this.resizeCharts(); window.addEventListener('resize', this.onWindowResize); this.scheduleRender() },
  beforeDestroy () { window.removeEventListener('resize', this.onWindowResize); if (this.resizeObserver) this.resizeObserver.disconnect(); Object.values(this.chartInstances).forEach(chart => chart && chart.dispose()) },
  methods: {
    groupFor (key) { return this.groups.find(group => group && group.key === key) || { status: 'UNAVAILABLE', metrics: [], series: [] } },
    latestFor (metric) { return (this.groupFor(this.definitionFor(metric).key).metrics || []).filter(item => item && item.metric === metric).sort((a, b) => String(a.effectiveAt || '').localeCompare(String(b.effectiveAt || ''))).pop() || null },
    definitionFor (metric) { return this.definitions.find(definition => definition.metrics.some(spec => spec.metric === metric)) || { key: '' } },
    chartEntries (groupKey) {
      const group = this.groupFor(groupKey)
      const grouped = new Map()
      for (const point of (Array.isArray(group.series) ? group.series : [])) {
        if (!point || !point.metric || !Number.isFinite(Number(point.value))) continue
        const key = `${point.metric}:${point.symbol || 'ALL'}`
        if (!grouped.has(key)) grouped.set(key, [])
        grouped.get(key).push(point)
      }
      return Array.from(grouped.entries()).slice(0, 4).map(([key, points]) => ({ key, symbol: String(points[0].symbol || ''), label: this.metricName(points[0].metric), points: points.slice(-365) }))
    },
    metricName (metric) { for (const definition of this.definitions) { const found = definition.metrics.find(spec => spec.metric === metric); if (found) return found.label } return String(metric || '').split('.').pop().replace(/_/gu, ' ') },
    instrumentLabel (metric) { return metric.symbol ? String(metric.symbol).toUpperCase() : 'ALL' },
    statusLabel (status) { return String(status || 'UNAVAILABLE') === 'AVAILABLE' ? (this.isVietnamese ? 'Có dữ liệu' : 'Available') : this.unavailableText },
    formatValue (value, unit) {
      const number = Number(value)
      if (!Number.isFinite(number)) return '—'
      const abs = Math.abs(number)
      const scaled = abs >= 1e12 ? [number / 1e12, 'T'] : abs >= 1e9 ? [number / 1e9, 'B'] : abs >= 1e6 ? [number / 1e6, 'M'] : abs >= 1e3 ? [number / 1e3, 'K'] : [number, '']
      return `${new Intl.NumberFormat(this.isVietnamese ? 'vi-VN' : 'en-US', { maximumFractionDigits: 2 }).format(scaled[0])}${scaled[1]}${unit && !['count', 'addresses', 'native'].includes(unit) ? ` ${unit}` : ''}`
    },
    formatDate (value) { return formatVietnamDate(value, { locale: this.isVietnamese ? 'vi-VN' : 'en-US' }) },
    scheduleRender () { this.$nextTick(() => this.renderCharts()) },
    resizeCharts () { Object.values(this.chartInstances).forEach(chart => chart && chart.resize()) },
    chartFor (key) { const raw = this.$refs[`chart_${key}`]; const element = Array.isArray(raw) ? raw[0] : raw; if (!element) return null; if (!this.resizeObserver && typeof ResizeObserver !== 'undefined') this.resizeObserver = new ResizeObserver(() => this.resizeCharts()); if (this.resizeObserver) this.resizeObserver.observe(element); return this.chartInstances[key] || echarts.init(element) },
    renderCharts () {
      for (const definition of this.definitions) {
        for (const entry of this.chartEntries(definition.key)) {
          const chart = this.chartFor(entry.key)
          if (!chart) continue
          this.chartInstances[entry.key] = chart
          chart.setOption({ animationDuration: 240, grid: { left: 12, right: 12, top: 14, bottom: 28 }, tooltip: { trigger: 'axis', backgroundColor: '#172033', borderWidth: 0, textStyle: { color: '#f8fafc' }, formatter: params => { const point = entry.points[params[0].dataIndex]; return `<strong>${this.formatDate(point.effectiveAt)}</strong><br>${entry.label}: ${this.formatValue(point.value, '')}` } }, xAxis: { type: 'category', data: entry.points.map(point => String(point.effectiveAt).slice(0, 10)), axisTick: { show: false }, axisLine: { lineStyle: { color: '#dce5f1' } }, axisLabel: { color: '#74829a', fontSize: 10, formatter: value => value.slice(5) } }, yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: '#eef2f7' } }, axisLabel: { color: '#74829a', fontSize: 10, formatter: value => this.formatValue(value, '') } }, series: [{ type: 'line', data: entry.points.map(point => point.value), smooth: true, showSymbol: false, lineStyle: { width: 2.5, color: '#3f78e0' }, areaStyle: { color: 'rgba(63,120,224,.10)' } }] }, true)
        }
      }
    }
  }
}
</script>

<style lang="less" scoped>
.onchain-terminal { margin-top: 14px; padding: 18px; border: 1px solid var(--line); border-radius: 13px; background: #f6f8fc; }.terminal-header, .group-header, .group-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }.terminal-header { align-items: flex-start; margin-bottom: 14px; }.terminal-header h3, .group-header h4 { margin: 0; color: var(--ink); font-weight: 750; }.terminal-header h3 { font-size: 23px; }.terminal-header p, .group-header p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }.terminal-header .ant-tag, .group-header .ant-tag { margin: 0; border-radius: 999px; }.onchain-group { margin-top: 12px; overflow: hidden; border: 1px solid var(--line); border-radius: 11px; background: var(--card); }.group-header { padding: 14px 16px; border-left: 4px solid #557eea; border-bottom: 1px solid var(--line); }.group-holders .group-header { border-left-color: #8758cc; }.group-liquidity .group-header { border-left-color: #109879; }.group-network .group-header { border-left-color: #d58535; }.group-heading { justify-content: flex-start; }.group-number { color: #7990ba; font-size: 11px; font-weight: 800; letter-spacing: .08em; }.group-header h4 { font-size: 17px; }.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; padding: 12px; }.metric-card { display: grid; gap: 5px; min-height: 106px; padding: 11px; border: 1px solid #dce4ef; border-radius: 9px; background: #fbfcfe; }.metric-card.unavailable { border-style: dashed; background: #f8fafc; }.metric-copy { display: flex; justify-content: space-between; gap: 5px; color: var(--muted); }.metric-copy small { color: #45546e; font-size: 12px; font-weight: 700; }.metric-copy span, .metric-status { font-size: 10px; }.metric-card strong { align-self: end; color: var(--ink); font-size: 19px; font-variant-numeric: tabular-nums; }.metric-card.unavailable strong { color: #a0aec0; }.metric-status { color: var(--muted); }.group-chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; padding: 0 12px 12px; }.chart-shell { overflow: hidden; border: 1px solid var(--line); border-radius: 9px; background: #fff; }.chart-shell header { display: flex; justify-content: space-between; gap: 8px; padding: 10px 12px 0; color: #34435e; font-size: 12px; font-weight: 700; }.chart-shell header small { color: #7b8aa3; font-size: 10px; }.onchain-chart { width: 100%; height: 205px; }.source-pending { display: flex; align-items: center; gap: 7px; min-height: 54px; padding: 0 14px; color: var(--muted); font-size: 12px; }
@media (max-width: 1100px) { .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } } @media (max-width: 720px) { .terminal-header, .group-header { align-items: flex-start; flex-direction: column; }.metric-grid, .group-chart-grid { grid-template-columns: 1fr; }.metric-card { min-height: 84px; } }
</style>
