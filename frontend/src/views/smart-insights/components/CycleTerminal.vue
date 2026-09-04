<template>
  <section class="cycle-terminal" aria-labelledby="cycle-terminal-title">
    <header class="cycle-terminal-header">
      <div>
        <h3 id="cycle-terminal-title">{{ $t('smartInsights.cycleTerminalTitle') }}</h3>
        <p>{{ $t('smartInsights.cycleTerminalDesc') }}</p>
      </div>
      <a-tag v-if="isCurrent" color="green"><i class="live-dot" />{{ $t('smartInsights.currentData') }}</a-tag>
    </header>

    <div v-if="altSeries.length" class="cycle-grid">

      <section class="altcoin-summary-row" aria-label="Altcoin Season summary">
        <article class="cycle-card alt-summary">
          <div class="card-title"><div><h4>{{ $t('smartInsights.altcoinSeason') }}</h4><small>{{ $t('smartInsights.cycleAltseasonRule') }}</small></div><a-tag>{{ $t('smartInsights.cycle90d') }}</a-tag></div>
          <div class="alt-summary-grid">
            <div class="alt-score"><span>{{ altClassification }}</span><strong>{{ formatIndex(altLatest && altLatest.value) }}</strong><small>{{ $t('smartInsights.cycleLatest') }} · {{ formatDate(altLatest && altLatest.date) }}</small></div>
            <div ref="seasonScale" class="season-scale" role="img" :aria-label="$t('smartInsights.altcoinSeason')" />
          </div>
        </article>

        <article class="cycle-card season-stat-card">
          <div class="card-title"><div><h4>{{ $t('smartInsights.cycleSeasonStats') }}</h4><small>{{ $t('smartInsights.cycleSeasonStatsDesc') }}</small></div></div>
          <table class="season-stats"><thead><tr><th></th><th>{{ $t('smartInsights.cycleAltcoin') }}</th><th>{{ $t('smartInsights.cycleBitcoin') }}</th></tr></thead><tbody>
            <tr v-for="row in statRows" :key="row.label"><th>{{ row.label }}</th><td>{{ row.alt }}</td><td>{{ row.btc }}</td></tr>
          </tbody></table>
        </article>
      </section>

      <article class="cycle-card chart-card full-width-card alt-history-card">
        <div class="card-title"><div><h4>{{ $t('smartInsights.cycleAltHistory') }}</h4><small>{{ $t('smartInsights.cycleAltHistoryDesc') }}</small></div><div class="range-controls"><button v-for="option in rangeOptions" :key="option" :class="{ active: altRange === option }" type="button" @click="altRange = option">{{ rangeLabel(option) }}</button></div></div>
        <div ref="altChart" class="cycle-chart" role="img" :aria-label="$t('smartInsights.cycleAltHistory')" />
      </article>

      <article class="cycle-card halving-context">
        <div class="card-title"><div><h4>Halving → Peak context</h4><small>{{ isVietnamese ? 'Bối cảnh chu kỳ lịch sử, không phải tín hiệu mua/bán.' : 'Historical cycle context, not a buy/sell signal.' }}</small></div><a-tag>{{ isVietnamese ? 'Bối cảnh' : 'Context' }}</a-tag></div>
        <div v-if="halvingHeight" class="halving-values"><div><small>{{ isVietnamese ? 'Block hiện tại' : 'Current block' }}</small><strong>{{ formatBlocks(halvingHeight) }}</strong></div><div><small>{{ isVietnamese ? 'Mốc halving kế tiếp' : 'Next halving block' }}</small><strong>{{ formatBlocks(nextHalvingBlock) }}</strong></div><div><small>{{ isVietnamese ? 'Còn lại' : 'Remaining blocks' }}</small><strong>{{ formatBlocks(blocksRemaining) }}</strong></div></div>
        <p v-else class="halving-empty">{{ sourceMissing }} · {{ isVietnamese ? 'Chờ block height đã xác thực để thêm bối cảnh.' : 'Waiting for a verified block height before adding context.' }}</p>
      </article>
    </div>
    <div v-else class="cycle-empty"><a-icon type="database" />{{ $t('smartInsights.noHistory') }}</div>
  </section>
</template>

<script>
import * as echarts from 'echarts'
import { formatVietnamDate } from '@/utils/vietnamTime'

const STAT_ROWS = [
  ['days_since_last_alt', 'days_since_last_btc', 'cycleDaysSince'],
  ['avg_gap_alt_to_alt', 'avg_gap_btc_to_btc', 'cycleAverageBetween'],
  ['longest_no_alt_streak', 'longest_no_btc_streak', 'cycleLongestWithout'],
  ['avg_alt_run', 'avg_btc_run', 'cycleAverageLength'],
  ['max_alt_run', 'max_btc_run', 'cycleLongestSeason'],
  ['altseasondays', 'bitcoinseasondays', 'cycleTotalDays']
]

export default {
  name: 'CycleTerminal',
  props: { cycle: { type: Object, default: () => ({}) }, isCurrent: { type: Boolean, default: false } },
  data () { return { altRange: '1Y', altChartInstance: null, scaleChartInstance: null, resizeObserver: null, onWindowResize: null } },
  computed: {
    locale () { return this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US' },
    rangeOptions () { return ['90D', '1Y', 'ALL'] },
    rawPoints () { return (Array.isArray(this.cycle.series) ? this.cycle.series : []).map(point => ({ metric: String(point && point.metric || ''), date: String(point && point.effectiveAt || '').slice(0, 10), value: Number(point && point.value) })).filter(point => point.date && Number.isFinite(point.value)).sort((left, right) => left.date.localeCompare(right.date)) },
    altSeries () { return this.rawPoints.filter(point => point.metric === 'crypto.cycle.altcoin_season.index') },
    altLatest () { return this.altSeries[this.altSeries.length - 1] || null },
    isVietnamese () { return this.locale === 'vi-VN' },
    sourceMissing () { return this.isVietnamese ? 'Nguồn chưa kết nối' : 'Source not connected' },
    halvingHeight () { const rows = this.cycle && this.cycle.halving && this.cycle.halving.metrics; const latest = Array.isArray(rows) ? rows.filter(row => row && row.metric === 'crypto.chain.block_height').sort((left, right) => String(left.effectiveAt || '').localeCompare(String(right.effectiveAt || ''))).pop() : null; const value = Number(latest && latest.value); return Number.isFinite(value) && value >= 0 ? Math.floor(value) : null },
    nextHalvingBlock () { return this.halvingHeight === null ? null : Math.ceil((this.halvingHeight + 1) / 210000) * 210000 },
    blocksRemaining () { return this.halvingHeight === null || this.nextHalvingBlock === null ? null : this.nextHalvingBlock - this.halvingHeight },
    statRows () { return STAT_ROWS.map(([alt, btc, label]) => ({ label: this.$t(`smartInsights.${label}`), alt: this.formatDays(this.stat(alt)), btc: this.formatDays(this.stat(btc)) })) },
    altClassification () { const value = this.altLatest && this.altLatest.value; if (!Number.isFinite(value)) return this.$t('smartInsights.dataUnavailableShort'); if (value >= 75) return this.$t('smartInsights.cycleAltSeason'); if (value <= 25) return this.$t('smartInsights.cycleBitcoinSeason'); return this.$t('smartInsights.cycleNotAltSeason') }
  },
  watch: {
    cycle: { deep: true, handler () { this.scheduleRender() } },
    altRange () { this.scheduleRender() }
  },
  mounted () { this.onWindowResize = () => this.resizeCharts(); window.addEventListener('resize', this.onWindowResize); this.scheduleRender() },
  beforeDestroy () { window.removeEventListener('resize', this.onWindowResize); if (this.resizeObserver) this.resizeObserver.disconnect(); [this.altChartInstance, this.scaleChartInstance].forEach(chart => chart && chart.dispose()) },
  methods: {
    stat (field) { const point = this.rawPoints.filter(item => item.metric === `crypto.cycle.altcoin_season.stat.${field}`).pop(); return point ? point.value : null },
    rangePoints (points, range) { const days = range === '90D' ? 90 : range === '1Y' ? 365 : null; return days ? points.slice(-days) : points },
    rangeLabel (option) { return option === 'ALL' ? this.$t('smartInsights.flowRangeAll') : option },
    formatIndex (value) { return Number.isFinite(Number(value)) ? new Intl.NumberFormat(this.locale, { maximumFractionDigits: 0 }).format(Number(value)) : '—' },
    formatDays (value) { return Number.isFinite(Number(value)) ? new Intl.NumberFormat(this.locale, { maximumFractionDigits: 1 }).format(Number(value)) : '—' },
    formatBlocks (value) { return Number.isFinite(Number(value)) ? new Intl.NumberFormat(this.locale, { maximumFractionDigits: 0 }).format(Number(value)) : '—' },
    formatDate (value) { return value ? formatVietnamDate(`${value}T00:00:00Z`, { locale: this.locale, fallback: value }) : '—' },
    formatShortDate (value) { return formatVietnamDate(`${value}T00:00:00Z`, { locale: this.locale, fallback: value, short: true }) },
    scheduleRender () { this.$nextTick(() => { this.renderSeasonScale(); this.renderAltChart() }) },
    resizeCharts () { [this.altChartInstance, this.scaleChartInstance].forEach(chart => chart && chart.resize()) },
    chartFor (ref, existing) {
      const raw = this.$refs[ref]
      const element = Array.isArray(raw) ? raw[0] : raw
      if (!element) return null
      if (!this.resizeObserver && typeof ResizeObserver !== 'undefined') this.resizeObserver = new ResizeObserver(() => this.resizeCharts())
      if (this.resizeObserver) this.resizeObserver.observe(element)
      return existing || echarts.init(element)
    },
    renderSeasonScale () {
      this.scaleChartInstance = this.chartFor('seasonScale', this.scaleChartInstance)
      if (!this.scaleChartInstance) return
      const current = this.altLatest && this.altLatest.value
      this.scaleChartInstance.setOption({ animationDuration: 240, grid: { left: 2, right: 2, top: 35, bottom: 27 }, xAxis: { type: 'category', data: Array.from({ length: 101 }, (_, index) => index), axisLabel: { color: '#64748b', fontSize: 10, formatter: value => value === 0 ? this.$t('smartInsights.cycleBitcoinSeason') : value === 100 ? this.$t('smartInsights.cycleAltSeason') : '' }, axisTick: { show: false }, axisLine: { show: false } }, yAxis: { show: false, min: 0, max: 1 }, visualMap: { show: false, dimension: 0, pieces: [{ lte: 25, color: '#f59e0b' }, { gt: 25, lte: 50, color: '#c4dc75' }, { gt: 50, lte: 74, color: '#5ba3b7' }, { gte: 75, color: '#df5959' }] }, series: [{ type: 'bar', data: Array.from({ length: 101 }, (_, index) => [index, 1]), barGap: '-100%', barCategoryGap: '0%', silent: true, itemStyle: { borderRadius: 0 }, markLine: Number.isFinite(current) ? { symbol: 'none', lineStyle: { color: '#14213d', width: 2 }, label: { formatter: this.formatIndex(current), color: '#14213d', fontSize: 21, fontWeight: 700, position: 'end' }, data: [{ xAxis: Math.round(current) }] } : undefined }] }, true)
    },
    renderAltChart () {
      this.altChartInstance = this.chartFor('altChart', this.altChartInstance)
      if (!this.altChartInstance) return
      this.altChartInstance.setOption(this.lineOption(this.rangePoints(this.altSeries, this.altRange), { area: true, seasonBands: true, color: '#25324a', title: this.$t('smartInsights.altcoinSeason') }), true)
    },
    lineOption (points, options) {
      const compact = Boolean(options.compact)
      return { animationDuration: 260, grid: compact ? { left: 8, right: 8, top: 8, bottom: 8 } : { left: 12, right: 16, top: 24, bottom: 34, containLabel: true }, tooltip: { trigger: 'axis', backgroundColor: '#182235', borderWidth: 0, textStyle: { color: '#f8fafc', fontSize: 12 }, formatter: params => { const point = points[params[0].dataIndex]; return `<strong>${this.formatDate(point.date)}</strong><br>${options.title}: ${this.formatIndex(point.value)}` } }, xAxis: { type: 'category', boundaryGap: false, data: points.map(point => point.date), axisTick: { show: false }, axisLine: { show: !compact, lineStyle: { color: '#dbe3ef' } }, axisLabel: { show: !compact, color: '#718096', fontSize: 11, formatter: value => this.formatShortDate(value) } }, yAxis: { type: 'value', min: options.seasonBands ? 0 : undefined, max: options.seasonBands ? 100 : undefined, show: !compact, splitLine: { show: !compact, lineStyle: { color: '#edf1f6' } }, axisLabel: { color: '#718096', fontSize: 11 } }, series: [{ type: 'line', smooth: true, showSymbol: false, lineStyle: { width: compact ? 2 : 2.5, color: options.color }, areaStyle: options.area ? { color: 'rgba(37,50,74,.09)' } : compact ? { color: `${options.color}18` } : undefined, data: points.map(point => point.value), markArea: options.seasonBands ? { silent: true, label: { color: '#64748b', fontSize: 11, fontWeight: 700 }, data: [[{ name: this.$t('smartInsights.cycleBitcoinSeason'), yAxis: 0, itemStyle: { color: 'rgba(245,158,11,.13)' } }, { yAxis: 25 }], [{ name: this.$t('smartInsights.cycleAltSeason'), yAxis: 75, itemStyle: { color: 'rgba(220,38,38,.10)' } }, { yAxis: 100 }]] } : undefined, markLine: options.seasonBands ? { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: '#a7b4c7' }, data: [{ yAxis: 25 }, { yAxis: 75 }] } : undefined }] }
    }
  }
}
</script>

<style lang="less" scoped>
.cycle-terminal { width: 100%; max-width: none; min-width: 0; box-sizing: border-box; margin-top: 14px; padding: 18px; border: 1px solid var(--line); border-radius: 13px; background: #f7f9fd; }
.cycle-terminal-header, .card-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.cycle-terminal h3, .cycle-terminal h4, .cycle-terminal h5 { margin: 0; color: var(--ink); font-weight: 750; }
.cycle-terminal h3 { font-size: 23px; }
.cycle-terminal h4 { font-size: 15px; }
.cycle-terminal h5 { font-size: 13px; }
.cycle-terminal p, .card-title small, .alt-score small { display: block; margin: 4px 0 0; color: var(--muted); font-size: 12px; }
.cycle-terminal-header { margin-bottom: 14px; }
.cycle-terminal-header .ant-tag, .card-title .ant-tag { margin: 0; border-radius: 999px; }
.live-dot { display: inline-block; width: 6px; height: 6px; margin-right: 5px; border-radius: 50%; background: #18a575; vertical-align: 1px; }
.cycle-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; width: 100%; min-width: 0; }
.cycle-card { min-width: 0; border: 1px solid var(--line); border-radius: 11px; background: var(--card); overflow: hidden; }
.card-title { padding: 14px 16px; border-bottom: 1px solid var(--line); }
.chart-card, .full-width-card { grid-column: 1 / -1; }
.range-controls { display: flex; flex-wrap: wrap; gap: 4px; }
.range-controls button { min-height: 27px; padding: 3px 8px; border: 1px solid var(--line); border-radius: 6px; color: var(--muted); background: var(--page-bg); font-size: 11px; cursor: pointer; }
.range-controls button.active { color: var(--ink); border-color: #bdcbe1; background: #e9eef7; box-shadow: 0 1px 3px rgba(20,35,60,.1); }
.cycle-chart { width: 100%; height: 310px; }
.altcoin-summary-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; min-width: 0; }
.altcoin-summary-row > .cycle-card { min-width: 0; }
.alt-summary-grid { display: grid; grid-template-columns: 180px minmax(0, 1fr); align-items: center; min-height: 174px; padding: 12px 16px 14px; }
.alt-score { display: grid; gap: 5px; }
.alt-score span { color: #4d7f3b; font-size: 13px; font-weight: 700; }
.alt-score strong { color: #16233d; font-size: 58px; line-height: 1; font-variant-numeric: tabular-nums; }
.season-scale { width: 100%; height: 142px; }
.season-stat-card { padding-bottom: 3px; }
.season-stats { width: 100%; border-collapse: collapse; font-size: 12px; }
.season-stats th, .season-stats td { padding: 8px 15px; border-bottom: 1px solid var(--line); text-align: right; font-variant-numeric: tabular-nums; }
.season-stats th:first-child { color: var(--muted); font-weight: 500; text-align: left; }
.season-stats thead th { color: var(--ink); font-size: 11px; }
.season-stats tbody tr:last-child > * { border-bottom: 0; }
.halving-context { background: linear-gradient(130deg, #fff 0%, #fafcff 100%); }
.halving-values { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); padding: 16px; }
.halving-values div { display: grid; gap: 5px; padding: 0 14px; border-right: 1px solid var(--line); }
.halving-values div:first-child { padding-left: 0; }
.halving-values div:last-child { border-right: 0; }
.halving-values small, .halving-empty { color: var(--muted); font-size: 12px; }
.halving-values strong { color: var(--ink); font-size: 23px; font-variant-numeric: tabular-nums; }
.halving-empty { min-height: 84px; padding: 27px 16px; }
.cycle-empty { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 180px; color: var(--muted); font-size: 13px; }
@media (max-width: 760px) {
  .altcoin-summary-row { grid-template-columns: 1fr; }
  .alt-summary-grid { grid-template-columns: 1fr; }
  .season-scale { height: 112px; }
  .card-title { flex-direction: column; }
  .range-controls { width: 100%; }
  .cycle-chart { height: 250px; }
  .halving-values { grid-template-columns: 1fr; gap: 12px; }
  .halving-values div, .halving-values div:first-child { padding: 0; border-right: 0; }
}
</style>
