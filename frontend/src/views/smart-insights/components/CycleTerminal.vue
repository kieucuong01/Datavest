<template>
  <section class="cycle-terminal" aria-labelledby="cycle-terminal-title">
    <header class="cycle-terminal-header">
      <div>
        <h3 id="cycle-terminal-title">{{ $t('smartInsights.cycleTerminalTitle') }}</h3>
        <p>{{ $t('smartInsights.cycleTerminalDesc') }}</p>
      </div>
      <a-tag color="green"><i class="live-dot" />{{ $t('smartInsights.currentData') }}</a-tag>
    </header>

    <div v-if="altSeries.length || cbbiSeries.length" class="cycle-grid">
      <article v-if="cbbiSeries.length" class="cycle-card chart-card full-width-card cbbi-main-card">
        <div class="card-title cbbi-main-title">
          <div>
            <span class="section-eyebrow">{{ $t('smartInsights.metricCbbi') }}</span>
            <h4>CBBI Confidence</h4>
            <small>{{ $t('smartInsights.cycleCbbiDesc') }}</small>
          </div>
          <div class="cbbi-focus-score">
            <small>{{ $t('smartInsights.cycleLatest') }}</small>
            <strong>{{ formatIndex(cbbiLatest && cbbiLatest.value) }}</strong>
            <span>{{ formatDate(cbbiLatest && cbbiLatest.date) }}</span>
          </div>
          <div class="range-controls"><button v-for="option in rangeOptions" :key="option" :class="{ active: cbbiRange === option }" type="button" @click="cbbiRange = option">{{ rangeLabel(option) }}</button></div>
        </div>
        <div ref="cbbiChart" class="cycle-chart cbbi-chart" role="img" :aria-label="cbbiTitle" />
      </article>

      <section v-if="cbbiComponentOptions.length" class="cbbi-components-section full-width-card" :aria-label="$t('smartInsights.metricCbbi')">
        <header class="component-section-header">
          <div><h4>{{ $t('smartInsights.metricCbbi') }} · {{ $t('smartInsights.cycleComponents') }}</h4><small>{{ $t('smartInsights.cycleCbbiDesc') }}</small></div>
          <span>{{ cbbiComponentOptions.length }} {{ $t('smartInsights.cycleComponents') }}</span>
        </header>
        <div class="cbbi-component-grid">
          <article v-for="(option, index) in cbbiComponentOptions" :key="option.key" class="cbbi-component-card">
            <div class="component-card-title">
              <span class="component-dot" :style="{ backgroundColor: componentColor(index) }" />
              <div><h5>{{ option.label }}</h5><small>{{ $t('smartInsights.cycleLatest') }} · {{ formatDate(componentLatest(option.key) && componentLatest(option.key).date) }}</small></div>
              <strong>{{ formatIndex(componentLatest(option.key) && componentLatest(option.key).value) }}</strong>
            </div>
            <div :ref="`componentChart_${option.key}`" class="component-chart" role="img" :aria-label="`${option.label} ${$t('smartInsights.cycleHistory')}`" />
          </article>
        </div>
      </section>

      <section class="price-cycle-models full-width-card" aria-label="Price-cycle models">
        <header class="component-section-header"><div><h4>Price-cycle models</h4><small>{{ isVietnamese ? 'Các mô hình được tách khỏi CBBI; chỉ Pi Cycle và 2-Year MA hiển thị khi component nguồn đã được import.' : 'Separated from CBBI; Pi Cycle and 2-Year MA appear only when their provider component has been imported.' }}</small></div></header>
        <div class="price-model-grid">
          <article v-for="model in priceModelOptions" :key="model.key" class="price-model-card" :class="{ unavailable: !modelLatest(model) }">
            <header><div><h5>{{ model.label }}</h5><small>{{ modelLatest(model) ? modelSourceLabel(model) : sourceMissing }}</small></div><strong>{{ modelLatest(model) ? formatModelValue(model, modelLatest(model).value) : '—' }}</strong></header>
            <div v-if="modelSeries(model).length" :ref="`modelChart_${model.key}`" class="model-chart" role="img" :aria-label="model.label" />
            <p v-else>{{ sourceMissing }}</p>
          </article>
        </div>
      </section>

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

const CBBI_LABELS = {
  confidence: 'CBBI', pi_cycle: 'Pi Cycle', rupl_nupl: 'RUPL / NUPL', rhodl: 'RHODL', puell: 'Puell', two_year_ma: '2Y MA', trolololo: 'Trolololo', mvrv: 'MVRV', reserve_risk: 'Reserve Risk', woobull: 'Woobull'
}
const COMPONENT_COLORS = ['#5e57d9', '#2385c7', '#a64ac9', '#e17c37', '#0d9488', '#d75772', '#667085', '#b45309', '#2563eb']
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
  props: { cycle: { type: Object, default: () => ({}) } },
  data () { return { altRange: '1Y', cbbiRange: '1Y', altChartInstance: null, cbbiChartInstance: null, componentChartInstances: {}, modelChartInstances: {}, scaleChartInstance: null, resizeObserver: null, onWindowResize: null } },
  computed: {
    locale () { return this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US' },
    rangeOptions () { return ['90D', '1Y', 'ALL'] },
    rawPoints () { return (Array.isArray(this.cycle.series) ? this.cycle.series : []).map(point => ({ metric: String(point && point.metric || ''), date: String(point && point.effectiveAt || '').slice(0, 10), value: Number(point && point.value) })).filter(point => point.date && Number.isFinite(point.value)).sort((left, right) => left.date.localeCompare(right.date)) },
    pricePoints () { return (this.cycle && this.cycle.priceHistory && Array.isArray(this.cycle.priceHistory.series) ? this.cycle.priceHistory.series : []).map(point => ({ date: String(point && point.effectiveAt || '').slice(0, 10), value: Number(point && point.value) })).filter(point => point.date && Number.isFinite(point.value) && point.value > 0).sort((left, right) => left.date.localeCompare(right.date)) },
    altSeries () { return this.rawPoints.filter(point => point.metric === 'crypto.cycle.altcoin_season.index') },
    altLatest () { return this.altSeries[this.altSeries.length - 1] || null },
    cbbiOptions () {
      const keys = new Set(this.rawPoints.filter(point => point.metric === 'crypto.cycle.cbbi.confidence' || point.metric.startsWith('crypto.cycle.cbbi.component.')).map(point => point.metric === 'crypto.cycle.cbbi.confidence' ? 'confidence' : point.metric.split('.').pop()))
      return ['confidence', ...Object.keys(CBBI_LABELS).filter(key => key !== 'confidence')].filter(key => keys.has(key)).map(key => ({ key, label: CBBI_LABELS[key] || key }))
    },
    cbbiSeries () { return this.rawPoints.filter(point => point.metric === 'crypto.cycle.cbbi.confidence') },
    cbbiLatest () { return this.cbbiSeries[this.cbbiSeries.length - 1] || null },
    cbbiComponentOptions () { return this.cbbiOptions.filter(option => option.key !== 'confidence') },
    priceModelOptions () { return [{ key: 'twoYear', label: '2-Year MA', unit: 'USD' }, { key: 'piCycle', label: 'Pi Cycle', unit: 'ratio' }, { key: 'twoHundredWma', label: '200WMA', unit: 'USD' }, { key: 'powerLaw', label: 'Power Law / Rainbow', unit: 'ratio' }] },
    priceModelData () { return { twoYear: this.movingAverage(this.pricePoints, 730), piCycle: this.piCycleRatio(this.pricePoints), twoHundredWma: this.movingAverage(this.pricePoints, 1_400), powerLaw: this.powerLawRatio(this.pricePoints) } },
    isVietnamese () { return this.locale === 'vi-VN' },
    sourceMissing () { return this.isVietnamese ? 'Nguồn chưa kết nối' : 'Source not connected' },
    halvingHeight () { const rows = this.cycle && this.cycle.halving && this.cycle.halving.metrics; const latest = Array.isArray(rows) ? rows.filter(row => row && row.metric === 'crypto.chain.block_height').sort((left, right) => String(left.effectiveAt || '').localeCompare(String(right.effectiveAt || ''))).pop() : null; const value = Number(latest && latest.value); return Number.isFinite(value) && value >= 0 ? Math.floor(value) : null },
    nextHalvingBlock () { return this.halvingHeight === null ? null : Math.ceil((this.halvingHeight + 1) / 210000) * 210000 },
    blocksRemaining () { return this.halvingHeight === null || this.nextHalvingBlock === null ? null : this.nextHalvingBlock - this.halvingHeight },
    cbbiTitle () { return `CBBI Confidence · ${this.$t('smartInsights.cycleHistory')}` },
    statRows () { return STAT_ROWS.map(([alt, btc, label]) => ({ label: this.$t(`smartInsights.${label}`), alt: this.formatDays(this.stat(alt)), btc: this.formatDays(this.stat(btc)) })) },
    altClassification () { const value = this.altLatest && this.altLatest.value; if (!Number.isFinite(value)) return this.$t('smartInsights.dataUnavailableShort'); if (value >= 75) return this.$t('smartInsights.cycleAltSeason'); if (value <= 25) return this.$t('smartInsights.cycleBitcoinSeason'); return this.$t('smartInsights.cycleNotAltSeason') }
  },
  watch: {
    cycle: { deep: true, handler () { this.scheduleRender() } },
    altRange () { this.scheduleRender() },
    cbbiRange () { this.scheduleRender() }
  },
  mounted () { this.onWindowResize = () => this.resizeCharts(); window.addEventListener('resize', this.onWindowResize); this.scheduleRender() },
  beforeDestroy () { window.removeEventListener('resize', this.onWindowResize); if (this.resizeObserver) this.resizeObserver.disconnect(); [this.altChartInstance, this.cbbiChartInstance, this.scaleChartInstance, ...Object.values(this.componentChartInstances), ...Object.values(this.modelChartInstances)].forEach(chart => chart && chart.dispose()) },
  methods: {
    stat (field) { const point = this.rawPoints.filter(item => item.metric === `crypto.cycle.altcoin_season.stat.${field}`).pop(); return point ? point.value : null },
    componentSeries (key) { return this.rawPoints.filter(point => point.metric === `crypto.cycle.cbbi.component.${key}`) },
    componentLatest (key) { const series = this.componentSeries(key); return series[series.length - 1] || null },
    modelSeries (model) { return model ? this.priceModelData[model.key] || [] : [] },
    modelLatest (model) { const series = this.modelSeries(model); return series[series.length - 1] || null },
    modelSourceLabel () { return this.isVietnamese ? 'CoinMetrics · PriceUSD hằng ngày · tính tại chỗ' : 'CoinMetrics · daily PriceUSD · calculated locally' },
    componentColor (index) { return COMPONENT_COLORS[index % COMPONENT_COLORS.length] },
    rangePoints (points, range) { const days = range === '90D' ? 90 : range === '1Y' ? 365 : null; return days ? points.slice(-days) : points },
    rangeLabel (option) { return option === 'ALL' ? this.$t('smartInsights.flowRangeAll') : option },
    formatIndex (value) { return Number.isFinite(Number(value)) ? new Intl.NumberFormat(this.locale, { maximumFractionDigits: 0 }).format(Number(value)) : '—' },
    formatDays (value) { return Number.isFinite(Number(value)) ? new Intl.NumberFormat(this.locale, { maximumFractionDigits: 1 }).format(Number(value)) : '—' },
    formatModelValue (model, value) { if (!Number.isFinite(Number(value))) return '—'; if (model && model.unit === 'USD') return `$${new Intl.NumberFormat(this.locale, { notation: 'compact', maximumFractionDigits: 2 }).format(Number(value))}`; return new Intl.NumberFormat(this.locale, { maximumFractionDigits: 2 }).format(Number(value)) },
    formatBlocks (value) { return Number.isFinite(Number(value)) ? new Intl.NumberFormat(this.locale, { maximumFractionDigits: 0 }).format(Number(value)) : '—' },
    formatDate (value) { return value ? formatVietnamDate(`${value}T00:00:00Z`, { locale: this.locale, fallback: value }) : '—' },
    formatShortDate (value) { return formatVietnamDate(`${value}T00:00:00Z`, { locale: this.locale, fallback: value, short: true }) },
    scheduleRender () { this.$nextTick(() => { this.renderSeasonScale(); this.renderAltChart(); this.renderCbbiChart(); this.renderComponentCharts(); this.renderModelCharts() }) },
    resizeCharts () { [this.altChartInstance, this.cbbiChartInstance, this.scaleChartInstance, ...Object.values(this.componentChartInstances), ...Object.values(this.modelChartInstances)].forEach(chart => chart && chart.resize()) },
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
    renderCbbiChart () {
      this.cbbiChartInstance = this.chartFor('cbbiChart', this.cbbiChartInstance)
      if (!this.cbbiChartInstance) return
      this.cbbiChartInstance.setOption(this.lineOption(this.rangePoints(this.cbbiSeries, this.cbbiRange), { color: '#5e57d9', title: this.cbbiTitle }), true)
    },
    renderComponentCharts () {
      this.cbbiComponentOptions.forEach((option, index) => {
        const ref = `componentChart_${option.key}`
        const chart = this.chartFor(ref, this.componentChartInstances[option.key])
        if (!chart) return
        this.componentChartInstances[option.key] = chart
        chart.setOption(this.lineOption(this.rangePoints(this.componentSeries(option.key), this.cbbiRange), { compact: true, color: this.componentColor(index), title: option.label }), true)
      })
    },
    renderModelCharts () {
      this.priceModelOptions.forEach((model, index) => {
        const points = this.rangePoints(this.modelSeries(model), this.cbbiRange)
        if (!points.length) return
        const ref = `modelChart_${model.key}`
        const chart = this.chartFor(ref, this.modelChartInstances[model.key])
        if (!chart) return
        this.modelChartInstances[model.key] = chart
        chart.setOption(this.lineOption(points, { compact: true, color: COMPONENT_COLORS[(index + 2) % COMPONENT_COLORS.length], title: model.label }), true)
      })
    },
    movingAverage (points, window) {
      if (!points.length) return []
      const output = []; let total = 0
      points.forEach((point, index) => { total += point.value; if (index >= window) total -= points[index - window].value; if (index >= window - 1) output.push({ date: point.date, value: total / window }) })
      return output
    },
    piCycleRatio (points) {
      const short = this.movingAverage(points, 111); const long = this.movingAverage(points, 350); const longByDate = new Map(long.map(point => [point.date, point.value]))
      return short.map(point => ({ date: point.date, value: point.value / (2 * longByDate.get(point.date)) })).filter(point => Number.isFinite(point.value))
    },
    powerLawRatio (points) {
      const epoch = Date.UTC(2009, 0, 3); const samples = points.map(point => ({ ...point, x: Math.log(Math.max(1, (Date.parse(`${point.date}T00:00:00Z`) - epoch) / 86_400_000)), y: Math.log(point.value) })).filter(point => Number.isFinite(point.x) && Number.isFinite(point.y))
      if (samples.length < 30) return []
      const count = samples.length; const sumX = samples.reduce((sum, point) => sum + point.x, 0); const sumY = samples.reduce((sum, point) => sum + point.y, 0); const sumXX = samples.reduce((sum, point) => sum + point.x * point.x, 0); const sumXY = samples.reduce((sum, point) => sum + point.x * point.y, 0); const denominator = count * sumXX - sumX * sumX
      if (!Number.isFinite(denominator) || denominator === 0) return []
      const slope = (count * sumXY - sumX * sumY) / denominator; const intercept = (sumY - slope * sumX) / count
      return samples.map(point => ({ date: point.date, value: point.value / Math.exp(intercept + slope * point.x) })).filter(point => Number.isFinite(point.value))
    },
    lineOption (points, options) {
      const compact = Boolean(options.compact)
      return { animationDuration: 260, grid: compact ? { left: 8, right: 8, top: 8, bottom: 8 } : { left: 12, right: 16, top: 24, bottom: 34, containLabel: true }, tooltip: { trigger: 'axis', backgroundColor: '#182235', borderWidth: 0, textStyle: { color: '#f8fafc', fontSize: 12 }, formatter: params => { const point = points[params[0].dataIndex]; return `<strong>${this.formatDate(point.date)}</strong><br>${options.title}: ${this.formatIndex(point.value)}` } }, xAxis: { type: 'category', boundaryGap: false, data: points.map(point => point.date), axisTick: { show: false }, axisLine: { show: !compact, lineStyle: { color: '#dbe3ef' } }, axisLabel: { show: !compact, color: '#718096', fontSize: 11, formatter: value => this.formatShortDate(value) } }, yAxis: { type: 'value', min: options.seasonBands ? 0 : undefined, max: options.seasonBands ? 100 : undefined, show: !compact, splitLine: { show: !compact, lineStyle: { color: '#edf1f6' } }, axisLabel: { color: '#718096', fontSize: 11 } }, series: [{ type: 'line', smooth: true, showSymbol: false, lineStyle: { width: compact ? 2 : 2.5, color: options.color }, areaStyle: options.area ? { color: 'rgba(37,50,74,.09)' } : compact ? { color: `${options.color}18` } : undefined, data: points.map(point => point.value), markArea: options.seasonBands ? { silent: true, label: { color: '#64748b', fontSize: 11, fontWeight: 700 }, data: [[{ name: this.$t('smartInsights.cycleBitcoinSeason'), yAxis: 0, itemStyle: { color: 'rgba(245,158,11,.13)' } }, { yAxis: 25 }], [{ name: this.$t('smartInsights.cycleAltSeason'), yAxis: 75, itemStyle: { color: 'rgba(220,38,38,.10)' } }, { yAxis: 100 }]] } : undefined, markLine: options.seasonBands ? { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: '#a7b4c7' }, data: [{ yAxis: 25 }, { yAxis: 75 }] } : undefined }] }
    }
  }
}
</script>

<style lang="less" scoped>
.cycle-terminal { width: 100%; max-width: none; min-width: 0; box-sizing: border-box; margin-top: 14px; padding: 18px; border: 1px solid var(--line); border-radius: 13px; background: #f7f9fd; }.cycle-terminal-header, .card-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }.cycle-terminal h3, .cycle-terminal h4, .cycle-terminal h5 { margin: 0; color: var(--ink); font-weight: 750; }.cycle-terminal h3 { font-size: 23px; }.cycle-terminal h4 { font-size: 15px; }.cycle-terminal h5 { font-size: 13px; }.cycle-terminal p, .card-title small, .alt-score small, .component-card-title small, .component-section-header small { display: block; margin: 4px 0 0; color: var(--muted); font-size: 12px; }.cycle-terminal-header { margin-bottom: 14px; }.cycle-terminal-header .ant-tag, .card-title .ant-tag { margin: 0; border-radius: 999px; }.live-dot { display: inline-block; width: 6px; height: 6px; margin-right: 5px; border-radius: 50%; background: #18a575; vertical-align: 1px; }.cycle-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; width: 100%; min-width: 0; }.cycle-card, .cbbi-components-section, .price-cycle-models { min-width: 0; border: 1px solid var(--line); border-radius: 11px; background: var(--card); overflow: hidden; }.card-title { padding: 14px 16px; border-bottom: 1px solid var(--line); }.chart-card, .cbbi-components-section, .price-cycle-models { grid-column: 1 / -1; }.cbbi-main-card { background: linear-gradient(136deg, #fff 0%, #fafaff 52%, #f4f5ff 100%); }.cbbi-main-title { align-items: center; }.section-eyebrow { display: block; margin-bottom: 4px; color: #6960d9; font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }.cbbi-focus-score { margin-left: auto; color: var(--muted); text-align: right; font-size: 11px; }.cbbi-focus-score small { display: block; }.cbbi-focus-score strong { display: block; color: #4d46bd; font-size: 30px; font-variant-numeric: tabular-nums; line-height: 1; }.cbbi-focus-score span { display: block; margin-top: 3px; font-size: 10px; }.range-controls { display: flex; flex-wrap: wrap; gap: 4px; }.range-controls button { min-height: 27px; padding: 3px 8px; border: 1px solid var(--line); border-radius: 6px; color: var(--muted); background: var(--page-bg); font-size: 11px; cursor: pointer; }.range-controls button.active { color: var(--ink); border-color: #bdcbe1; background: #e9eef7; box-shadow: 0 1px 3px rgba(20,35,60,.1); }.cycle-chart { width: 100%; height: 310px; }.cbbi-chart { height: 390px; }.component-section-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; border-bottom: 1px solid var(--line); }.component-section-header > span { color: var(--muted); font-size: 11px; }.cbbi-component-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }.cbbi-component-card { min-width: 0; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }.cbbi-component-card:nth-child(3n) { border-right: 0; }.cbbi-component-card:nth-last-child(-n + 3) { border-bottom: 0; }.component-card-title { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 12px 13px 0; }.component-dot { width: 7px; height: 7px; border-radius: 50%; }.component-card-title strong { color: var(--ink); font-size: 15px; font-variant-numeric: tabular-nums; }.component-chart { width: 100%; height: 125px; }.price-model-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }.price-model-card { min-width: 0; border-right: 1px solid var(--line); }.price-model-card:last-child { border-right: 0; }.price-model-card header { display: flex; justify-content: space-between; gap: 8px; padding: 12px 13px 0; }.price-model-card header small { display: block; margin-top: 4px; color: var(--muted); font-size: 10px; }.price-model-card header strong { color: #33415c; font-size: 18px; font-variant-numeric: tabular-nums; }.price-model-card.unavailable { background: #f9fafc; }.price-model-card.unavailable header strong { color: #a0aec0; }.price-model-card > p { min-height: 98px; padding: 27px 13px; color: var(--muted); font-size: 12px; }.model-chart { width: 100%; height: 118px; }.alt-summary-grid { display: grid; grid-template-columns: 180px minmax(0, 1fr); align-items: center; min-height: 174px; padding: 12px 16px 14px; }.alt-score { display: grid; gap: 5px; }.alt-score span { color: #4d7f3b; font-size: 13px; font-weight: 700; }.alt-score strong { color: #16233d; font-size: 58px; line-height: 1; font-variant-numeric: tabular-nums; }.season-scale { width: 100%; height: 142px; }.season-stat-card { padding-bottom: 3px; }.season-stats { width: 100%; border-collapse: collapse; font-size: 12px; }.season-stats th, .season-stats td { padding: 8px 15px; border-bottom: 1px solid var(--line); text-align: right; font-variant-numeric: tabular-nums; }.season-stats th:first-child { color: var(--muted); font-weight: 500; text-align: left; }.season-stats thead th { color: var(--ink); font-size: 11px; }.season-stats tbody tr:last-child > * { border-bottom: 0; }.halving-context { background: linear-gradient(130deg, #fff 0%, #fafcff 100%); }.halving-values { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); padding: 16px; }.halving-values div { display: grid; gap: 5px; padding: 0 14px; border-right: 1px solid var(--line); }.halving-values div:first-child { padding-left: 0; }.halving-values div:last-child { border-right: 0; }.halving-values small, .halving-empty { color: var(--muted); font-size: 12px; }.halving-values strong { color: var(--ink); font-size: 23px; font-variant-numeric: tabular-nums; }.halving-empty { min-height: 84px; padding: 27px 16px; }.cycle-empty { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 180px; color: var(--muted); font-size: 13px; }
@media (max-width: 920px) { .cbbi-component-grid, .price-model-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.cbbi-component-card:nth-child(3n) { border-right: 1px solid var(--line); }.cbbi-component-card:nth-child(2n), .price-model-card:nth-child(2n) { border-right: 0; }.cbbi-component-card:nth-last-child(-n + 3) { border-bottom: 1px solid var(--line); }.cbbi-component-card:nth-last-child(-n + 2) { border-bottom: 0; }.price-model-card:nth-child(-n + 2) { border-bottom: 1px solid var(--line); } }
@media (max-width: 760px) { .cycle-grid, .cbbi-component-grid, .price-model-grid { grid-template-columns: 1fr; }.alt-summary-grid { grid-template-columns: 1fr; }.season-scale { height: 112px; }.card-title { flex-direction: column; }.cbbi-main-title { align-items: flex-start; }.cbbi-focus-score { margin-left: 0; text-align: left; }.range-controls { width: 100%; }.cycle-chart { height: 250px; }.cbbi-chart { height: 300px; }.cbbi-component-card, .cbbi-component-card:nth-child(3n), .cbbi-component-card:nth-child(2n), .price-model-card, .price-model-card:nth-child(2n) { border-right: 0; border-bottom: 1px solid var(--line); }.cbbi-component-card:last-child, .price-model-card:last-child { border-bottom: 0; }.halving-values { grid-template-columns: 1fr; gap: 12px; }.halving-values div, .halving-values div:first-child { padding: 0; border-right: 0; } }
 .cycle-grid > .full-width-card, .cycle-grid > .altcoin-summary-row, .cycle-grid > .alt-history-card { grid-column: 1 / -1; width: 100%; } .altcoin-summary-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; min-width: 0; } .altcoin-summary-row > .cycle-card { min-width: 0; }
@media (max-width: 760px) { .altcoin-summary-row { grid-template-columns: 1fr; } }
.cycle-grid > .full-width-card, .cycle-grid > .altcoin-summary-row, .cycle-grid > .alt-history-card { grid-column: auto; }
</style>
