<template>
  <section class="derivatives-terminal" aria-labelledby="derivatives-terminal-title">
    <header class="terminal-header">
      <div><h3 id="derivatives-terminal-title">{{ text.title }}</h3><p>{{ text.desc }}</p></div>
      <a-tag :color="hasRows ? 'green' : 'orange'"><i class="live-dot" />{{ hasRows ? text.live : text.partial }}</a-tag>
    </header>

    <div v-if="hasRows" class="derivatives-layout">
      <aside class="asset-rail" :aria-label="text.assets">
        <h4>{{ text.assets }}</h4>
        <button v-for="asset in assets" :key="asset" type="button" :class="{ active: selectedAsset === asset }" @click="selectedAsset = asset">
          <span><i :class="`asset-dot ${asset.toLowerCase()}`" />{{ asset }}</span><strong>{{ latestFor('crypto.derivatives.perpetual.price_usd', asset) | money }}</strong>
        </button>
        <p>{{ text.sources }}: {{ sources.join(' · ') || '—' }}</p>
      </aside>

      <main class="derivatives-main">
        <div class="derivative-kpis">
          <article><span>{{ text.price }}</span><strong>{{ latestFor('crypto.derivatives.perpetual.price_usd') | money }}</strong><small>{{ latestDate('crypto.derivatives.perpetual.price_usd') }}</small></article>
          <article><span>{{ text.openInterest }}</span><strong>{{ latestFor('crypto.derivatives.perpetual.open_interest_usd') | money }}</strong><small>{{ historyNote('crypto.derivatives.perpetual.open_interest_usd') }}</small></article>
          <article><span>{{ text.funding }}</span><strong :class="fundingClass">{{ latestFor('crypto.derivatives.perpetual.funding_annualized') | percent }}</strong><small>{{ text.annualized }}</small></article>
          <article><span>{{ text.taker }}</span><strong :class="takerClass">{{ latestFor('crypto.derivatives.perpetual.taker_buy_sell_imbalance') | signedPercent }}</strong><small>{{ text.takerHint }}</small></article>
        </div>

        <article class="terminal-card price-card">
          <div class="card-heading"><div><h4>{{ selectedAsset }} · {{ text.positioning }}</h4><small>{{ text.positioningHint }}</small></div><div class="range-controls"><button v-for="value in ranges" :key="value" :class="{ active: range === value }" @click="range = value">{{ value }}</button></div></div>
          <div ref="priceChart" class="chart chart-large" />
        </article>

        <div class="chart-grid">
          <article class="terminal-card"><div class="card-heading"><div><h4>{{ text.funding }}</h4><small>{{ text.fundingHint }}</small></div></div><div ref="fundingChart" class="chart" /></article>
          <article class="terminal-card"><div class="card-heading"><div><h4>{{ text.taker }}</h4><small>{{ text.takerHint }}</small></div></div><div ref="takerChart" class="chart" /></article>
        </div>

        <section v-if="hasOptions" class="structure-grid">
          <article><span>{{ text.nearBasis }}</span><strong :class="valueClass(latestFor('crypto.derivatives.futures.near_term_annualized_basis'))">{{ latestFor('crypto.derivatives.futures.near_term_annualized_basis') | percent }}</strong><small>{{ text.deribitSource }}</small></article>
          <article><span>{{ text.farBasis }}</span><strong :class="valueClass(latestFor('crypto.derivatives.futures.far_term_annualized_basis'))">{{ latestFor('crypto.derivatives.futures.far_term_annualized_basis') | percent }}</strong><small>{{ text.deribitSource }}</small></article>
          <article><span>{{ text.putCall }}</span><strong>{{ latestFor('crypto.derivatives.options.put_call_open_interest_ratio') | ratio }}</strong><small>{{ text.optionsHint }}</small></article>
        </section>

        <article class="terminal-card history-card">
          <div class="card-heading"><div><h4>{{ text.history }}</h4><small>{{ text.historyHint }}</small></div></div>
          <div class="history-scroll"><table><thead><tr><th>{{ text.date }}</th><th>{{ text.price }}</th><th>{{ text.openInterest }}</th><th>{{ text.funding }}</th><th>{{ text.taker }}</th></tr></thead><tbody><tr v-for="row in tableRows" :key="row.date"><th>{{ formatDate(row.date) }}</th><td>{{ row.price | money }}</td><td>{{ row.oi | money }}</td><td :class="valueClass(row.funding)">{{ row.funding | percent }}</td><td :class="valueClass(row.taker)">{{ row.taker | signedPercent }}</td></tr></tbody></table></div>
        </article>
      </main>
    </div>
    <div v-else class="terminal-empty"><a-icon type="database" />{{ text.empty }}</div>
  </section>
</template>

<script>
import * as echarts from 'echarts'

const PRICE = 'crypto.derivatives.perpetual.price_usd'
const OI = 'crypto.derivatives.perpetual.open_interest_usd'
const FUNDING = 'crypto.derivatives.perpetual.funding_annualized'
const TAKER = 'crypto.derivatives.perpetual.taker_buy_sell_imbalance'

export default {
  name: 'DerivativesTerminal',
  filters: {
    money (value) { return Number.isFinite(Number(value)) ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 2 }).format(Number(value)) : '—' },
    percent (value) { return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(2)}%` : '—' },
    signedPercent (value) { return Number.isFinite(Number(value)) ? `${Number(value) >= 0 ? '+' : ''}${(Number(value) * 100).toFixed(1)}%` : '—' },
     ratio (value) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}×` : '—' }
  },
  props: { derivatives: { type: Object, default: () => ({}) } },
  data () { return { selectedAsset: 'BTC', range: '90D', charts: {}, resizeObserver: null, onResize: null } },
  computed: {
    isVi () { return !this.$i18n || String(this.$i18n.locale).startsWith('vi') },
    text () { return this.isVi ? { title: 'Phái sinh Terminal', desc: 'Theo dõi giá perpetual, open interest, funding và lực taker theo nguồn công khai.', live: 'DỮ LIỆU LIVE', partial: 'DỮ LIỆU MỘT PHẦN', assets: 'TÀI SẢN', sources: 'Nguồn', price: 'Giá perpetual', openInterest: 'Open interest', funding: 'Funding', taker: 'Taker buy/sell', annualized: 'Quy đổi năm', takerHint: 'Dương: bên mua chiếm ưu thế', positioning: 'Giá & Open Interest', positioningHint: 'Giá perpetual (đường) · OI USD (cột)', fundingHint: 'Funding quy đổi năm; không phải tín hiệu giao dịch', history: 'Lịch sử phái sinh', historyHint: 'Chỉ hiển thị điểm có dữ liệu nguồn', date: 'Ngày', empty: 'Chưa có lịch sử phái sinh đã xác thực', limited: 'Lịch sử nguồn giới hạn 30 ngày', nearBasis: 'Basis futures gần', farBasis: 'Basis futures xa', putCall: 'Put / Call OI', deribitSource: 'Deribit · snapshot hằng ngày', optionsHint: 'Cấu trúc vị thế options' } : { title: 'Derivatives Terminal', desc: 'Public-source perpetual price, open interest, funding and taker positioning.', live: 'LIVE DATA', partial: 'PARTIAL DATA', assets: 'ASSETS', sources: 'Sources', price: 'Perpetual price', openInterest: 'Open interest', funding: 'Funding', taker: 'Taker buy/sell', annualized: 'Annualized', takerHint: 'Positive: buy takers lead', positioning: 'Price & Open Interest', positioningHint: 'Perpetual price (line) · USD OI (bars)', fundingHint: 'Annualized funding; not a trading signal', history: 'Derivatives history', historyHint: 'Only source-backed points are displayed', date: 'Date', empty: 'No validated derivatives history', limited: 'Source history is limited to 30 days', nearBasis: 'Near futures basis', farBasis: 'Far futures basis', putCall: 'Put / Call OI', deribitSource: 'Deribit · daily snapshot', optionsHint: 'Options positioning structure' } },
    points () { return (Array.isArray(this.derivatives.series) ? this.derivatives.series : []).map(point => ({ ...point, date: String(point && point.effectiveAt || '').slice(0, 10), symbol: String(point && point.symbol || '').toUpperCase(), value: Number(point && point.value), historyLimited: String(point && point.source || '') === 'binance-usdm-derivatives' && [OI, TAKER].includes(String(point && point.metric || '')) })).filter(point => point.date && point.symbol && Number.isFinite(point.value)) },
    assets () { const available = [...new Set(this.points.filter(point => [PRICE, OI, FUNDING, TAKER].includes(point.metric)).map(point => point.symbol))]; return ['BTC', 'ETH', 'SOL'].filter(asset => available.includes(asset)) },
    hasRows () { return this.points.length > 0 },
    hasOptions () { return Number.isFinite(Number(this.latestFor('crypto.derivatives.options.put_call_open_interest_ratio'))) },
    sources () { return [...new Set(this.points.map(point => String(point.source || '')).filter(Boolean))] },
    ranges () { return ['7D', '30D', '90D', 'ALL'] },
    selectedPoints () { return this.points.filter(point => point.symbol === this.selectedAsset) },
    visibleDates () { const dates = [...new Set(this.selectedPoints.map(point => point.date))].sort(); const limit = { '7D': 7, '30D': 30, '90D': 90 }[this.range]; return limit ? dates.slice(-limit) : dates },
    visibleRows () { return this.visibleDates.map(date => ({ date, price: this.valueAt(PRICE, date), oi: this.valueAt(OI, date), funding: this.valueAt(FUNDING, date), taker: this.valueAt(TAKER, date) })) },
    tableRows () { return [...this.visibleRows].reverse() },
    fundingClass () { return this.valueClass(this.latestFor(FUNDING)) },
    takerClass () { return this.valueClass(this.latestFor(TAKER)) }
  },
  watch: { derivatives: { deep: true, handler () { this.ensureAsset(); this.renderAll() } }, selectedAsset () { this.renderAll() }, range () { this.renderAll() } },
  mounted () { this.ensureAsset(); this.onResize = () => Object.values(this.charts).forEach(chart => chart.resize()); window.addEventListener('resize', this.onResize); this.$nextTick(() => { this.renderAll(); if (typeof ResizeObserver !== 'undefined') { this.resizeObserver = new ResizeObserver(() => Object.values(this.charts).forEach(chart => chart.resize())); this.resizeObserver.observe(this.$el) } }) },
  beforeDestroy () { window.removeEventListener('resize', this.onResize); if (this.resizeObserver) this.resizeObserver.disconnect(); Object.values(this.charts).forEach(chart => chart.dispose()) },
  methods: {
    ensureAsset () { if (!this.assets.includes(this.selectedAsset)) this.selectedAsset = this.assets[0] || 'BTC' },
    metricPoints (metric) { return this.selectedPoints.filter(point => point.metric === metric && this.visibleDates.includes(point.date)).sort((a, b) => a.date.localeCompare(b.date)) },
    valueAt (metric, date) { const points = this.selectedPoints.filter(point => point.metric === metric && point.date === date); return points.length ? points[points.length - 1].value : null },
    latestFor (metric, asset = this.selectedAsset) { const points = this.points.filter(point => point.metric === metric && point.symbol === asset).sort((a, b) => a.date.localeCompare(b.date)); return points.length ? points[points.length - 1].value : null },
    latestDate (metric) { const points = this.selectedPoints.filter(point => point.metric === metric).sort((a, b) => a.date.localeCompare(b.date)); return points.length ? this.formatDate(points[points.length - 1].date) : '—' },
    historyNote (metric) { const point = this.selectedPoints.filter(item => item.metric === metric).slice(-1)[0]; return point && point.historyLimited ? this.text.limited : this.latestDate(metric) },
    valueClass (value) { return !Number.isFinite(Number(value)) ? '' : Number(value) > 0 ? 'positive' : Number(value) < 0 ? 'negative' : '' },
    formatDate (date) { const value = new Date(`${date}T00:00:00Z`); return Number.isNaN(value.getTime()) ? date : value.toLocaleDateString(this.isVi ? 'vi-VN' : 'en-US', { day: '2-digit', month: 'short', year: 'numeric' }) },
    shortDate (date) { const value = new Date(`${date}T00:00:00Z`); return Number.isNaN(value.getTime()) ? date : value.toLocaleDateString(this.isVi ? 'vi-VN' : 'en-US', { day: '2-digit', month: 'short' }) },
    renderAll () { this.$nextTick(() => { this.renderPrice(); this.renderMetric('fundingChart', FUNDING, '#7c5ce6', this.text.funding, value => `${(value * 100).toFixed(2)}%`); this.renderMetric('takerChart', TAKER, '#149f72', this.text.taker, value => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`) }) },
    baseOption (dates) { return { animationDuration: 260, grid: { left: 12, right: 15, top: 18, bottom: 30, containLabel: true }, tooltip: { trigger: 'axis', backgroundColor: '#182235', borderWidth: 0, textStyle: { color: '#f8fafc' } }, xAxis: { type: 'category', data: dates, axisTick: { show: false }, axisLine: { lineStyle: { color: '#dbe3ef' } }, axisLabel: { color: '#718096', fontSize: 11, formatter: value => this.shortDate(value) } }, yAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf1f6' } }, axisLabel: { color: '#718096', fontSize: 11 } } } },
    chartFor (ref) { if (!this.$refs[ref]) return null; if (!this.charts[ref]) this.charts[ref] = echarts.init(this.$refs[ref]); return this.charts[ref] },
    renderPrice () { const chart = this.chartFor('priceChart'); if (!chart) return; const rows = this.visibleRows; const option = this.baseOption(rows.map(row => row.date)); option.yAxis = [{ ...option.yAxis, name: 'USD', axisLabel: { color: '#718096', formatter: value => new Intl.NumberFormat('en-US', { notation: 'compact' }).format(value) } }, { type: 'value', name: 'OI', splitLine: { show: false }, axisLabel: { color: '#718096', formatter: value => new Intl.NumberFormat('en-US', { notation: 'compact' }).format(value) } }]; option.tooltip.formatter = params => { const row = rows[params[0].dataIndex]; return `<strong>${this.formatDate(row.date)}</strong><br>${this.text.price}: ${this.$options.filters.money(row.price)}<br>${this.text.openInterest}: ${this.$options.filters.money(row.oi)}` }; option.series = [{ name: this.text.openInterest, type: 'bar', yAxisIndex: 1, barMaxWidth: 18, itemStyle: { color: '#9db8ef', borderRadius: [3, 3, 0, 0] }, data: rows.map(row => row.oi) }, { name: this.text.price, type: 'line', smooth: true, showSymbol: false, lineStyle: { color: '#2b6de0', width: 2.6 }, areaStyle: { color: 'rgba(43,109,224,.10)' }, data: rows.map(row => row.price) }]; chart.setOption(option, true) },
    renderMetric (ref, metric, color, label, formatter) { const chart = this.chartFor(ref); if (!chart) return; const rows = this.visibleRows; const option = this.baseOption(rows.map(row => row.date)); option.tooltip.formatter = params => `<strong>${this.formatDate(rows[params[0].dataIndex].date)}</strong><br>${label}: ${formatter(params[0].value)}`; option.series = [{ type: 'bar', barMaxWidth: 18, data: rows.map(row => { const value = metric === FUNDING ? row.funding : row.taker; return { value, itemStyle: { color: Number(value) >= 0 ? color : '#db5d61', borderRadius: Number(value) >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3] } } }), markLine: { silent: true, symbol: 'none', lineStyle: { color: '#9aa8ba', type: 'dashed' }, data: [{ yAxis: 0 }] } }]; option.yAxis.axisLabel.formatter = formatter; chart.setOption(option, true) }
  }
}
</script>

<style lang="less" scoped>
.derivatives-terminal { margin-top: 14px; padding: 18px; border: 1px solid var(--line); border-radius: 13px; background: #f7f9fd; }.terminal-header, .card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }.terminal-header { margin-bottom: 14px; }.terminal-header h3, .terminal-header h4, .card-heading h4 { margin: 0; color: var(--ink); font-weight: 750; }.terminal-header h3 { font-size: 23px; }.card-heading h4 { font-size: 14px; }.terminal-header p, .card-heading small, .derivative-kpis small, .structure-grid small { display: block; margin: 4px 0 0; color: var(--muted); font-size: 12px; }.terminal-header .ant-tag { margin: 0; border-radius: 999px; }.live-dot { display: inline-block; width: 6px; height: 6px; margin-right: 5px; border-radius: 50%; background: #18a575; vertical-align: 1px; }.derivatives-layout { display: grid; grid-template-columns: 210px minmax(0, 1fr); gap: 16px; }.asset-rail, .terminal-card, .structure-grid article { border: 1px solid var(--line); border-radius: 10px; background: var(--card); }.asset-rail { padding: 12px; }.asset-rail h4 { margin: 3px 0 9px; color: var(--muted); font-size: 11px; }.asset-rail button { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 33px; padding: 5px 8px; border: 0; border-radius: 6px; color: var(--ink); background: transparent; font-size: 12px; cursor: pointer; }.asset-rail button:hover, .asset-rail button.active { background: #e8edf6; }.asset-rail button span { display: flex; align-items: center; gap: 7px; }.asset-rail strong { font-size: 11px; font-variant-numeric: tabular-nums; }.asset-rail p { margin: 13px 3px 1px; color: var(--muted); font-size: 10px; line-height: 1.5; word-break: break-word; }.asset-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; }.asset-dot.btc { background: #f59e0b; }.asset-dot.eth { background: #818cf8; }.asset-dot.sol { background: #a78bfa; }.derivatives-main { min-width: 0; }.derivative-kpis, .structure-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }.derivative-kpis article, .structure-grid article { display: grid; gap: 7px; min-height: 92px; padding: 13px; }.derivative-kpis span, .structure-grid span { color: var(--muted); font-size: 11px; text-transform: uppercase; }.derivative-kpis strong, .structure-grid strong { color: var(--ink); font-size: 20px; font-variant-numeric: tabular-nums; }.structure-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 12px; }.positive { color: #14944f !important; }.negative { color: #d2263d !important; }.terminal-card { overflow: hidden; }.card-heading { padding: 13px 15px; border-bottom: 1px solid var(--line); }.range-controls { display: flex; gap: 4px; padding: 3px; border: 1px solid var(--line); border-radius: 7px; background: var(--page-bg); }.range-controls button { min-height: 26px; padding: 3px 8px; border: 0; border-radius: 5px; background: transparent; color: var(--muted); font-size: 11px; cursor: pointer; }.range-controls button.active { color: var(--ink); background: var(--card); box-shadow: 0 1px 3px rgba(20,35,60,.12); }.chart { width: 100%; height: 238px; }.chart-large { height: 310px; }.chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }.history-card { margin-top: 12px; }.history-scroll { overflow-x: auto; }.history-scroll table { width: 100%; min-width: 700px; border-collapse: collapse; font-size: 11px; }.history-scroll th, .history-scroll td { padding: 9px 12px; border-bottom: 1px solid var(--line); text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }.history-scroll th:first-child { text-align: left; color: var(--muted); background: #f2f5fa; font-weight: 600; }.history-scroll thead th { color: var(--muted); font-size: 10px; text-transform: uppercase; }.terminal-empty { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 180px; color: var(--muted); font-size: 13px; } @media (max-width: 980px) { .derivatives-layout { grid-template-columns: 1fr; }.asset-rail { display: flex; gap: 4px; flex-wrap: wrap; }.asset-rail h4, .asset-rail p { width: 100%; }.asset-rail button { width: auto; flex: 1; }.asset-rail p { display: none; } } @media (max-width: 680px) { .derivatives-terminal { padding: 13px; }.terminal-header, .card-heading { flex-direction: column; }.derivative-kpis, .chart-grid, .structure-grid { grid-template-columns: 1fr; }.chart-large { height: 250px; } }
</style>
