<template>
  <article class="pulse-trend-chart">
    <div class="chart-heading">
      <div>
        <h4>{{ title }}</h4>
        <small v-if="latest">{{ currentLabel }}: {{ formatValue(latest.value) }} · {{ formatDate(latest.effectiveAt) }}</small>
      </div>
      <a-tag v-if="status && status !== 'AVAILABLE'" :class="statusClass">{{ statusLabel }}</a-tag>
    </div>
    <div v-if="interactive" class="chart-controls" aria-label="ETF chart controls">
      <div class="chart-control-group" role="group" :aria-label="$t('smartInsights.flowMode')">
        <button
          v-for="option in modeOptions"
          :key="option.value"
          type="button"
          :class="{ active: mode === option.value }"
          :aria-pressed="mode === option.value"
          @click="mode = option.value">{{ option.label }}</button>
      </div>
      <div class="chart-control-group range-controls" role="group" :aria-label="$t('smartInsights.flowRange')">
        <button
          v-for="option in rangeOptions"
          :key="option.value"
          type="button"
          :class="{ active: range === option.value }"
          :aria-pressed="range === option.value"
          @click="range = option.value">{{ option.label }}</button>
      </div>
    </div>
    <div v-if="!chartPoints.length" class="chart-empty">
      <a-icon type="line-chart" />
      <span>{{ $t('smartInsights.noHistory') }}</span>
    </div>
    <div v-else ref="chart" class="trend-chart" role="img" :aria-label="title" />
    <div v-if="chartPoints.length" class="chart-footnote"><span>{{ rangeLabel }}</span><span>{{ chartPoints.length }} {{ $t('smartInsights.observations') }}</span></div>
  </article>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'PulseTrendChart',
  props: {
    title: { type: String, default: '' },
    series: { type: Array, default: () => [] },
    status: { type: String, default: 'AVAILABLE' },
    unit: { type: String, default: '' },
    variant: { type: String, default: 'line' },
    interactive: { type: Boolean, default: false }
  },
  data () {
    return { mode: 'flow', range: '30D', chart: null, resizeObserver: null, onWindowResize: null }
  },
  computed: {
    locale () { return this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US' },
    primaryColor () { return (this.$store && this.$store.state.app.color) || '#2b6de0' },
    points () {
      return this.series
        .map(item => ({ value: Number(item && item.value), effectiveAt: item && item.effectiveAt }))
        .filter(item => Number.isFinite(item.value) && item.effectiveAt)
        .sort((left, right) => new Date(left.effectiveAt).getTime() - new Date(right.effectiveAt).getTime())
    },
    visiblePoints () {
      const limits = { '7D': 7, '30D': 30, '90D': 90 }
      return limits[this.range] ? this.points.slice(-limits[this.range]) : this.points
    },
    chartPoints () {
      if (!this.interactive || this.mode === 'flow') return this.visiblePoints
      let cumulative = 0
      return this.visiblePoints.map(point => {
        cumulative += point.value
        return { ...point, value: cumulative }
      })
    },
    latest () { return this.chartPoints.length ? this.chartPoints[this.chartPoints.length - 1] : null },
    modeOptions () { return [{ value: 'flow', label: this.$t('smartInsights.flowModeNet') }, { value: 'cumulative', label: this.$t('smartInsights.flowModeCumulative') }] },
    rangeOptions () { return ['7D', '30D', '90D', 'ALL'].map(value => ({ value, label: value === 'ALL' ? this.$t('smartInsights.flowRangeAll') : value })) },
    currentLabel () {
      if (!this.interactive) return this.$t('smartInsights.latestValue')
      return this.mode === 'cumulative' ? this.$t('smartInsights.flowModeCumulative') : this.$t('smartInsights.metricNetFlow')
    },
    rangeLabel () { return this.range === 'ALL' ? this.$t('smartInsights.flowRangeAll') : this.range },
    statusClass () { return `chart-status-${String(this.status || '').toLowerCase()}` },
    statusLabel () {
      const labels = { AVAILABLE: this.$t('smartInsights.availableStatus'), PARTIAL: this.$t('smartInsights.partialStatus'), STALE: this.$t('smartInsights.stale'), UNAVAILABLE: this.$t('smartInsights.unavailableShort') }
      return labels[String(this.status || 'UNAVAILABLE').toUpperCase()] || this.$t('smartInsights.unavailableShort')
    }
  },
  watch: {
    series: { deep: true, handler () { this.scheduleRender() } },
    mode () { this.scheduleRender() },
    range () { this.scheduleRender() },
    variant () { this.scheduleRender() },
    primaryColor () { this.scheduleRender() }
  },
  mounted () {
    this.onWindowResize = () => this.chart && this.chart.resize()
    window.addEventListener('resize', this.onWindowResize)
    this.scheduleRender()
  },
  beforeDestroy () {
    window.removeEventListener('resize', this.onWindowResize)
    if (this.resizeObserver) this.resizeObserver.disconnect()
    if (this.chart) this.chart.dispose()
  },
  methods: {
    scheduleRender () { this.$nextTick(() => this.renderChart()) },
    renderChart () {
      if (!this.chartPoints.length || !this.$refs.chart) {
        if (this.chart) this.chart.clear()
        return
      }
      if (!this.chart) {
        this.chart = echarts.init(this.$refs.chart)
        if (typeof ResizeObserver !== 'undefined') {
          this.resizeObserver = new ResizeObserver(() => this.chart && this.chart.resize())
          this.resizeObserver.observe(this.$refs.chart)
        }
      }
      const cumulative = this.interactive && this.mode === 'cumulative'
      this.chart.setOption({
        animationDuration: 260,
        grid: { left: 8, right: 12, top: 18, bottom: 28, containLabel: true },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: cumulative ? 'line' : 'shadow' },
          backgroundColor: '#182235',
          borderWidth: 0,
          textStyle: { color: '#f8fafc', fontSize: 12 },
          formatter: params => {
            const point = params && params[0]
            if (!point) return ''
            const item = this.chartPoints[point.dataIndex]
            return `<strong>${this.formatDate(item.effectiveAt)}</strong><br>${this.currentLabel}: ${this.formatValue(item.value)}`
          }
        },
        xAxis: {
          type: 'category',
data: this.chartPoints.map(point => point.effectiveAt),
boundaryGap: !cumulative,
          axisLine: { lineStyle: { color: '#dbe3ef' } },
axisTick: { show: false },
          axisLabel: { color: '#718096', fontSize: 11, formatter: value => this.formatDateShort(value) }
        },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf1f6' } }, axisLabel: { color: '#718096', fontSize: 11, formatter: value => this.formatCompact(value) } },
        series: [{
          name: this.currentLabel,
          type: cumulative ? 'line' : (this.variant === 'bar' ? 'bar' : 'line'),
          smooth: cumulative || this.variant !== 'bar',
showSymbol: false,
barMaxWidth: 18,
          data: this.chartPoints.map(point => cumulative || this.variant !== 'bar' ? point.value : { value: point.value, itemStyle: { color: point.value >= 0 ? '#159f72' : '#db5d61', borderRadius: point.value >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3] } }),
          lineStyle: { width: 2.5, color: this.primaryColor },
itemStyle: { color: this.primaryColor },
          areaStyle: cumulative ? { color: this.primaryColor, opacity: 0.1 } : undefined,
          markLine: !cumulative && this.variant === 'bar' ? { silent: true, symbol: 'none', lineStyle: { color: '#9aa8ba', type: 'dashed' }, data: [{ yAxis: 0 }] } : undefined
        }]
      }, true)
    },
    formatCompact (value) { return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(Number(value)) },
    formatValue (value) {
      if (!Number.isFinite(Number(value))) return '—'
      const number = Number(value)
      if (this.unit === 'USD') return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 2 }).format(number)
      return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(number)}${this.unit ? ` ${this.unit}` : ''}`
    },
    formatDate (value) {
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? String(value || '—') : date.toLocaleDateString(this.locale, { day: '2-digit', month: 'short', year: 'numeric' })
    },
    formatDateShort (value) {
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? String(value || '') : date.toLocaleDateString(this.locale, { day: '2-digit', month: 'short' })
    }
  }
}
</script>

<style lang="less" scoped>
.pulse-trend-chart { min-width: 0; padding: 15px 15px 10px; border: 1px solid var(--line); border-radius: 12px; background: var(--card); }
.chart-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.chart-heading h4 { margin: 0; color: var(--ink); font-size: 16px; font-weight: 700; }
.chart-heading small { display: block; margin-top: 5px; color: var(--muted); font-size: 12px; }
.chart-heading .ant-tag { margin: 0; font-size: 10px; }
.chart-status-unavailable { color: var(--muted); }
.chart-status-partial { color: #b78117; }
.chart-controls { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 13px; }
.chart-control-group { display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 8px; background: var(--page-bg); }
.chart-control-group button { min-height: 27px; padding: 3px 8px; border: 0; border-radius: 5px; color: var(--muted); background: transparent; font-size: 11px; font-weight: 600; cursor: pointer; }
.chart-control-group button.active { color: var(--ink); background: var(--card); box-shadow: 0 1px 3px rgba(20, 35, 60, .12); }
.chart-control-group button:focus-visible { outline: 2px solid var(--blue); outline-offset: 1px; }
.trend-chart { width: 100%; height: 230px; margin-top: 6px; }
.chart-empty { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 230px; color: var(--muted); font-size: 13px; }
.chart-footnote { display: flex; justify-content: space-between; color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
@media (max-width: 480px) { .chart-controls { align-items: flex-start; flex-direction: column; } .range-controls { width: 100%; } .range-controls button { flex: 1; } }
</style>
