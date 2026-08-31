<template>
  <section v-if="points.length" class="fear-greed-panel" :aria-label="$t('smartInsights.fearGreedTitle')">
    <div class="fear-greed-top">
      <article class="fear-greed-card gauge-card">
        <div class="fear-heading">
          <span class="bitcoin-mark"><a-icon type="bitcoin" /></span>
          <div><h3>{{ $t('smartInsights.fearGreedTitle') }}</h3><p>{{ $t('smartInsights.fearGreedDesc') }}</p></div>
        </div>
        <div class="current-reading"><span>{{ $t('smartInsights.fearGreedNow') }}:</span> <strong :class="toneClass(latest.value)">{{ sentiment(latest.value) }}</strong></div>
        <div ref="gauge" class="fear-gauge" role="img" :aria-label="`${$t('smartInsights.fearGreedTitle')}: ${latest.value}`" />
        <footer><span>{{ sourceName }}</span><span>{{ $t('smartInsights.lastUpdated') }}: {{ formatDate(latest.effectiveAt) }}</span></footer>
      </article>
      <article class="fear-greed-card historical-card" aria-label="Historical Values">
        <h3>{{ $t('smartInsights.fearGreedHistory') }}</h3>
        <div v-for="row in historyRows" :key="row.label" class="historical-row">
          <div><span>{{ row.label }}</span><strong :class="toneClass(row.point.value)">{{ sentiment(row.point.value) }}</strong></div>
          <b :class="toneClass(row.point.value)">{{ Math.round(row.point.value) }}</b>
        </div>
      </article>
    </div>
    <article class="fear-greed-card history-chart-card">
      <div class="history-chart-heading"><div><h3>{{ $t('smartInsights.fearGreedOverTime') }}</h3><p>{{ $t('smartInsights.fearGreedChartDesc') }}</p></div></div>
      <div class="fear-range-controls" role="group" :aria-label="$t('smartInsights.flowRange')">
        <button
          v-for="option in rangeOptions"
          :key="option.value"
          type="button"
          :class="{ active: range === option.value }"
          :aria-pressed="range === option.value"
          @click="range = option.value">{{ option.label }}</button>
      </div>
      <div ref="trend" class="fear-trend" role="img" :aria-label="$t('smartInsights.fearGreedOverTime')" />
    </article>
  </section>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'FearGreedPanel',
  props: { fear: { type: Object, default: () => ({}) } },
  data () { return { range: '30D', gaugeChart: null, trendChart: null, resizeObserver: null, onWindowResize: null } },
  computed: {
    locale () { return this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US' },
    points () {
      return (Array.isArray(this.fear.series) ? this.fear.series : [])
        .map(point => ({ effectiveAt: point && point.effectiveAt, value: Number(point && point.value) }))
        .filter(point => point.effectiveAt && Number.isFinite(point.value) && point.value >= 0 && point.value <= 100)
        .sort((left, right) => new Date(left.effectiveAt).getTime() - new Date(right.effectiveAt).getTime())
    },
    latest () { return this.points[this.points.length - 1] },
    sourceName () { return (this.fear.sources && this.fear.sources[0] && this.fear.sources[0].source) || 'alternative.me' },
    rangeOptions () { return [{ value: '7D', label: this.$t('smartInsights.fearGreed7Days') }, { value: '30D', label: this.$t('smartInsights.fearGreed1Month') }, { value: '90D', label: this.$t('smartInsights.fearGreed3Months') }, { value: '365D', label: this.$t('smartInsights.fearGreed1Year') }, { value: 'ALL', label: this.$t('smartInsights.flowRangeAll') }] },
    visiblePoints () {
      const limits = { '7D': 7, '30D': 30, '90D': 90, '365D': 365 }
      return limits[this.range] ? this.points.slice(-limits[this.range]) : this.points
    },
    historyRows () {
      return [{ label: this.$t('smartInsights.fearGreedNow'), days: 0 }, { label: this.$t('smartInsights.fearGreedYesterday'), days: 1 }, { label: this.$t('smartInsights.fearGreedLastWeek'), days: 7 }, { label: this.$t('smartInsights.fearGreedLastMonth'), days: 30 }]
        .map(item => ({ ...item, point: this.pointDaysAgo(item.days) }))
        .filter(item => item.point)
    }
  },
  watch: {
    fear: { deep: true, handler () { this.scheduleRender() } },
    range () { this.scheduleRender() }
  },
  mounted () {
    this.onWindowResize = () => { if (this.gaugeChart) this.gaugeChart.resize(); if (this.trendChart) this.trendChart.resize() }
    window.addEventListener('resize', this.onWindowResize)
    this.scheduleRender()
  },
  beforeDestroy () {
    window.removeEventListener('resize', this.onWindowResize)
    if (this.resizeObserver) this.resizeObserver.disconnect()
    if (this.gaugeChart) this.gaugeChart.dispose()
    if (this.trendChart) this.trendChart.dispose()
  },
  methods: {
    scheduleRender () { this.$nextTick(() => this.renderCharts()) },
    renderCharts () {
      if (!this.latest || !this.$refs.gauge || !this.$refs.trend) return
      if (!this.gaugeChart) this.gaugeChart = echarts.init(this.$refs.gauge)
      if (!this.trendChart) {
        this.trendChart = echarts.init(this.$refs.trend)
        if (typeof ResizeObserver !== 'undefined') {
          this.resizeObserver = new ResizeObserver(this.onWindowResize)
          this.resizeObserver.observe(this.$refs.trend)
        }
      }
      this.gaugeChart.setOption({
        animationDuration: 400,
        series: [{
          type: 'gauge',
startAngle: 210,
endAngle: -30,
min: 0,
max: 100,
splitNumber: 4,
          axisLine: { lineStyle: { width: 19, color: [[0.25, '#db7040'], [0.45, '#e9b34f'], [0.55, '#aeb7c1'], [0.75, '#a9d64d'], [1, '#69bd5a']] } },
          pointer: { length: '62%', width: 5, itemStyle: { color: '#6c7884' } },
anchor: { show: true, size: 13, itemStyle: { color: '#fff', borderColor: '#7b8792', borderWidth: 4 } },
          axisTick: { show: false },
splitLine: { show: false },
axisLabel: { show: false },
title: { show: false },
          detail: { valueAnimation: true, offsetCenter: [0, '29%'], fontSize: 31, fontWeight: 700, color: this.toneColor(this.latest.value), formatter: '{value}' },
          data: [{ value: Math.round(this.latest.value) }]
        }]
      }, true)
      this.trendChart.setOption({
        animationDuration: 280,
        grid: { left: 10, right: 18, top: 26, bottom: 45, containLabel: true },
        tooltip: { trigger: 'axis', axisPointer: { type: 'line' }, backgroundColor: '#182235', borderWidth: 0, textStyle: { color: '#f8fafc', fontSize: 12 }, formatter: params => { const point = this.visiblePoints[params[0].dataIndex]; return `<strong>${this.formatDate(point.effectiveAt)}</strong><br>${this.$t('smartInsights.fearGreedTitle')}: ${Math.round(point.value)} · ${this.sentiment(point.value)}` } },
        xAxis: { type: 'category', data: this.visiblePoints.map(point => point.effectiveAt), boundaryGap: false, axisLine: { lineStyle: { color: '#dbe3ef' } }, axisTick: { show: false }, axisLabel: { color: '#718096', fontSize: 11, formatter: value => this.formatDateShort(value) } },
        yAxis: { type: 'value', min: 0, max: 100, interval: 20, name: this.$t('smartInsights.value'), nameTextStyle: { color: '#718096' }, splitLine: { lineStyle: { color: '#edf1f6' } }, axisLabel: { color: '#718096', fontSize: 11 } },
        series: [{ type: 'line', name: this.$t('smartInsights.fearGreedTitle'), data: this.visiblePoints.map(point => point.value), smooth: true, showSymbol: this.visiblePoints.length <= 100, symbolSize: 6, lineStyle: { width: 3, color: '#b7bdc4' }, itemStyle: { color: '#b7bdc4' }, areaStyle: { color: 'rgba(183,189,196,.10)' } }]
      }, true)
    },
    pointDaysAgo (days) {
      const target = new Date(this.latest.effectiveAt).getTime() - days * 86400000
      return [...this.points].reverse().find(point => new Date(point.effectiveAt).getTime() <= target) || this.points[0]
    },
    sentiment (value) {
      if (value < 25) return this.$t('smartInsights.fearGreedExtremeFear')
      if (value < 45) return this.$t('smartInsights.fearGreedFear')
      if (value < 56) return this.$t('smartInsights.fearGreedNeutral')
      if (value < 75) return this.$t('smartInsights.fearGreedGreed')
      return this.$t('smartInsights.fearGreedExtremeGreed')
    },
    toneClass (value) { return `tone-${value < 25 ? 'extreme-fear' : value < 45 ? 'fear' : value < 56 ? 'neutral' : value < 75 ? 'greed' : 'extreme-greed'}` },
    toneColor (value) { return value < 25 ? '#d96d3d' : value < 45 ? '#e5a744' : value < 56 ? '#718096' : value < 75 ? '#91bb34' : '#57a24e' },
    formatDate (value) { const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value || '—') : date.toLocaleDateString(this.locale, { day: '2-digit', month: 'short', year: 'numeric' }) },
    formatDateShort (value) { const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value || '') : date.toLocaleDateString(this.locale, { day: '2-digit', month: 'short' }) }
  }
}
</script>

<style lang="less" scoped>
.fear-greed-panel { display: grid; gap: 14px; margin-top: 14px; }
.fear-greed-top { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; }
.fear-greed-card { border: 1px solid var(--line); border-radius: 12px; background: var(--card); box-shadow: 0 3px 12px var(--blue-ring); }
.gauge-card { overflow: hidden; padding: 17px 17px 11px; }
.fear-heading { display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
.bitcoin-mark { display: inline-grid; place-items: center; flex: 0 0 31px; width: 31px; height: 31px; border-radius: 50%; color: #fff; background: #f4a640; font-size: 18px; }
.fear-heading h3, .historical-card h3, .history-chart-heading h3 { margin: 0; color: var(--ink); font-size: 20px; font-weight: 700; }
.fear-heading p, .history-chart-heading p { margin: 2px 0 0; color: var(--muted); font-size: 13px; }
.current-reading { margin-top: 10px; text-align: right; color: var(--ink); font-size: 15px; }
.current-reading strong { font-size: 17px; }
.fear-gauge { width: 100%; height: 205px; margin-top: -5px; }
.gauge-card footer { display: flex; justify-content: space-between; gap: 8px; padding-top: 7px; border-top: 1px solid var(--line); color: var(--muted); font-size: 11px; }
.historical-card { padding: 20px 22px 12px; }
.historical-row { display: flex; align-items: center; justify-content: space-between; min-height: 57px; border-bottom: 1px solid var(--line); }
.historical-row:last-child { border-bottom: 0; }
.historical-row div { display: grid; gap: 2px; color: var(--ink); font-size: 15px; }
.historical-row strong { font-size: 16px; }
.historical-row b { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 50%; color: #fff; font-size: 21px; font-weight: 500; }
.tone-extreme-fear { color: #d66a3a; }.historical-row b.tone-extreme-fear { background: #d66a3a; }
.tone-fear { color: #d89d37; }.historical-row b.tone-fear { background: #d89d37; }
.tone-neutral { color: #718096; }.historical-row b.tone-neutral { background: #718096; }
.tone-greed { color: #91bb34; }.historical-row b.tone-greed { background: #91bb34; }
.tone-extreme-greed { color: #57a24e; }.historical-row b.tone-extreme-greed { background: #57a24e; }
.history-chart-card { padding: 20px 22px 12px; }
.fear-range-controls { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 15px; }
.fear-range-controls button { min-height: 36px; padding: 7px 14px; border: 1px solid #e8a3a3; border-radius: 6px; color: #b94c4e; background: #fff7f7; font-size: 13px; font-weight: 600; cursor: pointer; }
.fear-range-controls button.active { border-color: #e85f63; color: #fff; background: #e85f63; }
.fear-range-controls button:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
.fear-trend { width: 100%; height: 330px; margin-top: 8px; }
@media (max-width: 780px) { .fear-greed-top { grid-template-columns: 1fr; } }
@media (max-width: 480px) { .gauge-card footer { align-items: flex-start; flex-direction: column; } .history-chart-card, .historical-card { padding: 16px; } .fear-range-controls button { flex: 1; padding: 7px 8px; } }
</style>
