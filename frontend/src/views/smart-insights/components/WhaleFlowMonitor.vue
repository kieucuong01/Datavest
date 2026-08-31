<template>
  <section class="whale-flow-monitor" aria-labelledby="whale-flow-title">
    <header class="whale-flow-heading">
      <div>
        <h3 id="whale-flow-title">{{ $t('smartInsights.whaleFlowTitle') }}</h3>
        <p>{{ $t('smartInsights.whaleFlowDesc') }}</p>
      </div>
      <a-tag :color="statusColor">{{ statusLabel }}</a-tag>
    </header>

    <div class="whale-summary-grid">
      <article class="whale-signal" :class="toneClass">
        <span>{{ $t('smartInsights.whaleSignal') }}</span>
        <strong>{{ toneLabel }}</strong>
        <small>{{ $t('smartInsights.whaleSignalGuardrail') }}</small>
      </article>
      <article>
        <span>{{ $t('smartInsights.whaleCohortChange') }}</span>
        <strong :class="valueClass(cohortChange && cohortChange.value)">{{ formatBtc(cohortChange && cohortChange.value) }}</strong>
        <small>{{ formatDate(cohortChange && cohortChange.effectiveAt) }}</small>
      </article>
      <article>
        <span>{{ $t('smartInsights.whaleMatchedChange') }}</span>
        <strong :class="valueClass(matchedChange && matchedChange.value)">{{ formatBtc(matchedChange && matchedChange.value) }}</strong>
        <small>{{ $t('smartInsights.whaleMatchedChangeHint') }}</small>
      </article>
      <article>
        <span>{{ $t('smartInsights.whaleExchangeNetflow') }}</span>
        <strong :class="valueClass(exchangeNetflow && -exchangeNetflow.value)">{{ formatBtc(exchangeNetflow && exchangeNetflow.value) }}</strong>
        <small>{{ $t('smartInsights.whaleExchangeNetflowHint') }}</small>
      </article>
      <article>
        <span>{{ $t('smartInsights.whaleIncrease') }}</span>
        <strong class="positive">{{ formatBtc(increase && increase.value) }}</strong>
        <small>{{ formatAddressCount(accumulatingCount) }}</small>
      </article>
      <article>
        <span>{{ $t('smartInsights.whaleDecrease') }}</span>
        <strong class="negative">{{ formatBtc(decrease && decrease.value) }}</strong>
        <small>{{ formatAddressCount(distributingCount) }}</small>
      </article>
      <article>
        <span>{{ $t('smartInsights.whaleConcentration') }}</span>
        <strong>{{ formatPercent(top10Share && top10Share.value) }}</strong>
        <small>{{ $t('smartInsights.whaleConcentrationHint') }}</small>
      </article>
      <article>
        <span>{{ $t('smartInsights.whaleDataQuality') }}</span>
        <strong>{{ formatPercent(quality.labelCoverage) }}</strong>
        <small>{{ qualityDetail }}<span v-if="quality.flowCoverage != null"> · {{ $t('smartInsights.whaleFlowCoverage') }} {{ formatPercent(quality.flowCoverage) }}</span></small>
      </article>
    </div>

    <p class="whale-disclaimer"><a-icon type="info-circle" />{{ $t('smartInsights.whaleDisclaimer') }}</p>
    <p v-if="detail.addressCount" class="whale-detail-note"><a-icon type="profile" />{{ $t('smartInsights.whaleDetailCoverage', { count: detail.addressCount }) }}</p>

    <div class="whale-chart-grid">
      <pulse-trend-chart
        :title="$t('smartInsights.whaleCohortChart')"
        :series="cohortSeries"
        :status="whaleFlow.status"
        unit="BTC"
        variant="bar"
        interactive
      />
      <pulse-trend-chart
        :title="$t('smartInsights.whaleExchangeChart')"
        :series="exchangeSeries"
        :status="whaleFlow.status"
        unit="BTC"
        variant="bar"
        interactive
      />
    </div>

    <section v-if="movers.accumulating.length || movers.distributing.length" class="whale-movers">
      <header class="whale-subheading">
        <div>
          <h4>{{ $t('smartInsights.whaleMoversTitle') }}</h4>
          <p>{{ $t('smartInsights.whaleMoversDesc') }} <span v-if="movers.effectiveAt">· {{ formatDate(movers.effectiveAt) }}</span></p>
        </div>
        <span class="whale-mover-legend">{{ $t('smartInsights.whaleMoverLegend') }}</span>
      </header>
      <div class="whale-mover-grid">
        <div class="whale-mover-panel">
          <h5 class="positive">{{ $t('smartInsights.whaleTopAccumulators') }}</h5>
          <table v-if="movers.accumulating.length" class="whale-mover-table">
            <thead><tr><th>{{ $t('smartInsights.whaleAddress') }}</th><th>{{ $t('smartInsights.whaleRank') }}</th><th>{{ $t('smartInsights.whaleBalance') }}</th><th>{{ $t('smartInsights.whaleDelta') }}</th></tr></thead>
            <tbody><tr v-for="item in movers.accumulating" :key="`in-${item.address}`">
              <td><code>{{ shortAddress(item.address) }}</code><small>{{ item.label || item.entityCategory || $t('smartInsights.whaleUnknownEntity') }}</small></td>
              <td>#{{ item.rank || '—' }}</td><td>{{ formatBtc(item.balance, false) }}</td><td class="positive">{{ formatBtc(item.value) }}</td>
            </tr></tbody>
          </table>
          <p v-else class="whale-mover-empty">{{ $t('smartInsights.whaleNoMovers') }}</p>
        </div>
        <div class="whale-mover-panel">
          <h5 class="negative">{{ $t('smartInsights.whaleTopDistributors') }}</h5>
          <table v-if="movers.distributing.length" class="whale-mover-table">
            <thead><tr><th>{{ $t('smartInsights.whaleAddress') }}</th><th>{{ $t('smartInsights.whaleRank') }}</th><th>{{ $t('smartInsights.whaleBalance') }}</th><th>{{ $t('smartInsights.whaleDelta') }}</th></tr></thead>
            <tbody><tr v-for="item in movers.distributing" :key="`out-${item.address}`">
              <td><code>{{ shortAddress(item.address) }}</code><small>{{ item.label || item.entityCategory || $t('smartInsights.whaleUnknownEntity') }}</small></td>
              <td>#{{ item.rank || '—' }}</td><td>{{ formatBtc(item.balance, false) }}</td><td class="negative">{{ formatBtc(item.value) }}</td>
            </tr></tbody>
          </table>
          <p v-else class="whale-mover-empty">{{ $t('smartInsights.whaleNoMovers') }}</p>
        </div>
      </div>
    </section>
    <div v-if="sources.length" class="whale-sources">
      <span>{{ $t('smartInsights.sources') }}:</span>
      <a v-for="source in sources" :key="source.source" :href="source.sourceUrl" target="_blank" rel="noopener noreferrer">{{ source.source }}</a>
    </div>
  </section>
</template>

<script>
import PulseTrendChart from './PulseTrendChart'

export default {
  name: 'WhaleFlowMonitor',
  components: { PulseTrendChart },
  props: { whaleFlow: { type: Object, default: () => ({}) } },
  computed: {
    locale () { return this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US' },
    insight () { return this.whaleFlow.insight || {} },
    quality () { return this.whaleFlow.quality || {} },
    cohort () { return this.whaleFlow.cohort || {} },
    movers () { return this.whaleFlow.movers || { accumulating: [], distributing: [] } },
    detail () { return this.whaleFlow.detail || {} },
    sources () { return Array.isArray(this.whaleFlow.sources) ? this.whaleFlow.sources : [] },
    cohortChange () { return this.cohort.latestChange || null },
    matchedChange () { return this.cohort.latestMatchedChange || null },
    increase () { return this.cohort.latestIncrease || null },
    decrease () { return this.cohort.latestDecrease || null },
    top10Share () { return this.cohort.latestTop10Share || null },
    accumulatingCount () { return this.whaleMetric('crypto.large_address.accumulating_address_count') },
    distributingCount () { return this.whaleMetric('crypto.large_address.distributing_address_count') },
    exchangeNetflow () { return (this.whaleFlow.exchangePressure || {}).latestNetflow || null },
    cohortSeries () { return this.pointsFor('crypto.large_address.balance_change_btc') },
    exchangeSeries () { return this.pointsFor('crypto.onchain.exchange_netflow_native') },
    toneClass () { return `tone-${String(this.insight.tone || 'INSUFFICIENT').toLowerCase()}` },
    toneLabel () {
      const labels = {
        ACCUMULATION: this.$t('smartInsights.whaleAccumulation'),
        DISTRIBUTION: this.$t('smartInsights.whaleDistribution'),
        MIXED: this.$t('smartInsights.whaleMixed'),
        INSUFFICIENT: this.$t('smartInsights.whaleInsufficient')
      }
      return labels[String(this.insight.tone || 'INSUFFICIENT').toUpperCase()] || labels.INSUFFICIENT
    },
    statusLabel () {
      const labels = {
        AVAILABLE: this.$t('smartInsights.availableStatus'),
        PARTIAL: this.$t('smartInsights.partialStatus'),
        UNAVAILABLE: this.$t('smartInsights.unavailableShort')
      }
      return labels[String(this.whaleFlow.status || 'UNAVAILABLE').toUpperCase()] || labels.UNAVAILABLE
    },
    statusColor () { return this.whaleFlow.status === 'AVAILABLE' ? 'green' : this.whaleFlow.status === 'PARTIAL' ? 'orange' : 'default' },
    qualityDetail () {
      const tracked = Number(this.quality.trackedAddressCount)
      const excluded = Number(this.quality.excludedAddressCount)
      if (!Number.isFinite(tracked)) return this.$t('smartInsights.whaleQualityHeuristic')
      return this.$t('smartInsights.whaleQualityDetail', { tracked: Math.round(tracked), excluded: Number.isFinite(excluded) ? Math.round(excluded) : 0 })
    }
  },
  methods: {
    pointsFor (metric) {
      return (Array.isArray(this.whaleFlow.series) ? this.whaleFlow.series : []).filter(point => point && point.metric === metric)
    },
    whaleMetric (metric) {
      const points = this.pointsFor(metric)
      return points.length ? points[points.length - 1] : null
    },
    valueClass (value) {
      const number = Number(value)
      return Number.isFinite(number) ? (number > 0 ? 'positive' : number < 0 ? 'negative' : 'neutral') : 'neutral'
    },
    formatBtc (value, signed = true) {
      const number = Number(value)
      if (!Number.isFinite(number)) return '—'
      return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 0, signDisplay: signed ? 'always' : 'auto' }).format(number)} BTC`
    },
    formatAddressCount (point) {
      const number = Number(point && point.value)
      return Number.isFinite(number) ? this.$t('smartInsights.whaleAddressCount', { count: Math.round(number) }) : this.$t('smartInsights.noHistory')
    },
    shortAddress (value) {
      const address = String(value || '')
      return address.length > 13 ? `${address.slice(0, 6)}…${address.slice(-5)}` : address || '—'
    },
    formatPercent (value) {
      const number = Number(value)
      return Number.isFinite(number) ? `${new Intl.NumberFormat(this.locale, { style: 'percent', maximumFractionDigits: 0 }).format(number)}` : '—'
    },
    formatDate (value) {
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? this.$t('smartInsights.dataUnavailableShort') : date.toLocaleDateString(this.locale, { day: '2-digit', month: 'short', year: 'numeric' })
    }
  }
}
</script>

<style lang="less" scoped>
.whale-flow-monitor { margin-top: 14px; padding: 18px; border: 1px solid var(--line); border-radius: 13px; background: linear-gradient(135deg, #f7f9fd 0%, #fbfcff 60%, #f2f7ff 100%); }
.whale-flow-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }.whale-flow-heading h3 { margin: 0; color: var(--ink); font-size: 21px; font-weight: 750; }.whale-flow-heading p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }.whale-flow-heading .ant-tag { margin: 0; border-radius: 999px; }
.whale-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }.whale-summary-grid article { display: grid; gap: 7px; min-height: 102px; padding: 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--card); }.whale-summary-grid span { color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .02em; }.whale-summary-grid strong { color: var(--ink); font-size: 20px; font-variant-numeric: tabular-nums; }.whale-summary-grid small { color: var(--muted); font-size: 11px; line-height: 1.35; }.whale-signal { border-color: #d7e3fa !important; background: linear-gradient(135deg, #eff5ff, #fff) !important; }.tone-accumulation strong { color: #11834a; }.tone-distribution strong { color: #c63743; }.tone-mixed strong, .tone-insufficient strong { color: #8a6b20; }.positive { color: #14944f !important; }.negative { color: #d2263d !important; }.neutral { color: var(--muted) !important; }
.whale-disclaimer, .whale-detail-note { display: flex; gap: 7px; margin: 11px 2px 0; color: #6d7888; font-size: 12px; line-height: 1.45; }.whale-disclaimer .anticon, .whale-detail-note .anticon { margin-top: 2px; color: #5576a8; }.whale-chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 13px; }.whale-movers { margin-top: 13px; padding: 14px; border: 1px solid var(--line); border-radius: 11px; background: var(--card); }.whale-subheading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; padding-bottom: 10px; border-bottom: 1px solid var(--line); }.whale-subheading h4 { margin: 0; color: var(--ink); font-size: 16px; }.whale-subheading p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }.whale-mover-legend { color: var(--muted); font-size: 11px; }.whale-mover-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 12px; }.whale-mover-panel { min-width: 0; }.whale-mover-panel h5 { margin: 0 0 6px; font-size: 13px; }.whale-mover-table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 11px; }.whale-mover-table th, .whale-mover-table td { padding: 8px 5px; border-bottom: 1px solid var(--line); text-align: right; font-variant-numeric: tabular-nums; }.whale-mover-table th { color: var(--muted); font-size: 10px; text-transform: uppercase; }.whale-mover-table th:first-child, .whale-mover-table td:first-child { width: 42%; text-align: left; }.whale-mover-table td:first-child { overflow: hidden; }.whale-mover-table code { display: block; overflow: hidden; color: var(--ink); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; text-overflow: ellipsis; white-space: nowrap; }.whale-mover-table td small { display: block; overflow: hidden; color: var(--muted); text-overflow: ellipsis; white-space: nowrap; }.whale-mover-table tbody tr:last-child td { border-bottom: 0; }.whale-mover-empty { margin: 0; padding: 18px 5px; color: var(--muted); font-size: 12px; }
.whale-sources { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 11px; color: var(--muted); font-size: 11px; }.whale-sources a { color: var(--blue); }
@media (max-width: 900px) { .whale-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.whale-chart-grid, .whale-mover-grid { grid-template-columns: 1fr; } }
@media (max-width: 540px) { .whale-flow-monitor { padding: 13px; }.whale-flow-heading { flex-direction: column; }.whale-summary-grid { grid-template-columns: 1fr; } }
</style>
