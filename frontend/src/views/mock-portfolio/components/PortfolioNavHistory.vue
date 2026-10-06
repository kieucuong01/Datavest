<template>
  <section class="nav-history">
    <h2>{{ $t('portfolioBook.navTitle') }}</h2><p>{{ $t('portfolioBook.navDisclosure') }}</p>
    <div class="history-toolbar"><label>{{ $t('portfolioBook.startDate') }}<input v-model="start" type="date"></label><label>{{ $t('portfolioBook.endDate') }}<input v-model="end" type="date" :max="yesterday"></label><button :disabled="loading" @click="load">{{ $t('portfolioBook.loadHistory') }}</button><button :disabled="loading || !start || !end" @click="refresh">{{ $t('portfolioBook.refreshHistory') }}</button></div>
    <a-radio-group v-model="timeframe" size="small"><a-radio-button value="1w">1W</a-radio-button><a-radio-button value="1m">1M</a-radio-button><a-radio-button value="ytd">YTD</a-radio-button><a-radio-button value="all">{{ $t('portfolioBook.all') }}</a-radio-button></a-radio-group>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="!visiblePoints.length">{{ $t('portfolioBook.navEmpty') }}</p>
    <template v-else><p>{{ $t('portfolioBook.navTitle') }}: <strong>{{ latest?.nav ?? '—' }} {{ currency }}</strong> · {{ $t('portfolioBook.valuedNav') }}: {{ latest?.valuedNav ?? '—' }} {{ currency }} · {{ $t('portfolioBook.coverage') }}: {{ latest?.coverage }}</p><p>{{ $t('portfolioBook.dietz') }}: {{ lastReturn === null ? '—' : (Number(lastReturn) * 100).toFixed(2) + '%' }}<span v-if="latest?.returnReason"> · {{ reasonLabel(latest.returnReason) }}</span></p><div ref="chart" class="nav-chart" role="img" :aria-label="$t('portfolioBook.navTitle')" /><details><summary>{{ $t('portfolioBook.priceEvidence') }}</summary><div v-for="position in latest?.positions || []" :key="position.market + position.symbol"><strong>{{ position.symbol }}</strong> · {{ position.quote.source || '—' }} · {{ position.quote.tradeDate || '—' }} · {{ position.valuationStatus }}<small>{{ position.quote.checksum || '—' }}</small></div></details></template>
  </section>
</template>
<script>
import * as echarts from 'echarts'
import { bookHistory, refreshBookHistory } from '@/api/portfolio-books'
import { filterHistory, navChartOptions, vietnamDay } from '../portfolioHistory'
export default {
  props: { bookId: { type: String, required: true }, currency: { type: String, required: true }, revision: { type: Number, required: true } },
  data () { const today = vietnamDay(); const yesterday = new Date(today + 'T00:00:00Z'); yesterday.setUTCDate(yesterday.getUTCDate() - 1); const start = new Date(yesterday); start.setUTCDate(start.getUTCDate() - 89); return { start: start.toISOString().slice(0, 10), end: yesterday.toISOString().slice(0, 10), yesterday: yesterday.toISOString().slice(0, 10), points: [], timeframe: 'all', loading: false, error: '', ticket: 0, chartInstance: null } },
  computed: {
    visiblePoints () { return filterHistory(this.points, this.timeframe) },
    latest () { return this.visiblePoints[this.visiblePoints.length - 1] },
    lastReturn () { if (!this.visiblePoints.length || this.visiblePoints[0]?.cumulativeReturn == null || this.latest?.cumulativeReturn == null) return null; return (1 + Number(this.latest.cumulativeReturn)) / (1 + Number(this.visiblePoints[0].cumulativeReturn)) - 1 }
  },
  watch: { revision () { this.load() }, timeframe () { this.render() }, bookId () { this.points = []; this.load() } },
  mounted () { this.load(); window.addEventListener('resize', this.resize) },
  beforeDestroy () { this.ticket++; this.chartInstance?.dispose(); window.removeEventListener('resize', this.resize) },
  methods: {
    reasonLabel (reason) { return this.$t('portfolioBook.' + ({ large_flow_requires_valuation: 'largeFlow', missing_valuation: 'missingValuation', non_positive_capital: 'noCapital', invalid_or_missing_valuation: 'missingValuation' }[reason] || 'missingValuation')) },
    async request (refresh) { const ticket = ++this.ticket; const id = this.bookId; const revision = this.revision; this.loading = true; this.error = ''; try { const result = await (refresh ? refreshBookHistory(id, { start: this.start, end: this.end }) : bookHistory(id, { start: this.start, end: this.end })); if (ticket === this.ticket && id === this.bookId && revision === this.revision && result.data.revision === revision) { this.points = result.data.points; this.$nextTick(this.render) } } catch (e) { if (ticket === this.ticket) this.error = e.response?.data?.message || this.$t('portfolioBook.error') } finally { if (ticket === this.ticket) this.loading = false } },
    load () { return this.request(false) },
    refresh () { return this.request(true) },
    render () { if (!this.$refs.chart) { this.chartInstance?.dispose(); this.chartInstance = null; return }; if (!this.chartInstance) this.chartInstance = echarts.init(this.$refs.chart); this.chartInstance.setOption(navChartOptions(this.visiblePoints), true); this.chartInstance.resize() },
    resize () { this.chartInstance?.resize() }
  }
}
</script>
<style scoped>.nav-history{margin:24px 0;padding:20px;border:1px solid #8290a540;border-radius:12px}.history-toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}label{display:grid;gap:5px}input,button{padding:8px;border:1px solid #8290a5;border-radius:6px;background:transparent;color:inherit}.nav-chart{height:290px;width:100%}small{display:block;overflow-wrap:anywhere;font-size:10px}p[role=alert]{color:#dc2626}</style>
