<template>
  <section class="market-pulse" aria-labelledby="market-pulse-title">
    <div class="section-title-row">
      <div>
        <h2 id="market-pulse-title">{{ $t('smartInsights.marketRhythm') }} <a-tag>{{ $t('smartInsights.currentData') }}</a-tag></h2>
        <p>{{ $t('smartInsights.marketRhythmDesc') }}</p>
      </div>
      <a-tag :color="pulse.status === 'AVAILABLE' ? 'green' : 'orange'">{{ statusLabel(pulse.status) }}</a-tag>
    </div>
    <div class="pulse-tabs" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        role="tab"
        :aria-selected="activeKey === tab.key"
        :class="{ active: activeKey === tab.key }"
        @click="activeKey = tab.key"
      >
        {{ tabLabel(tab) }}
      </button>
    </div>
    <section class="legacy-card pulse-summary">
      <div class="card-heading compact-heading">
        <div><h3>{{ tabLabel(activeTab) }}</h3><p>{{ $t('smartInsights.sourceBackedOnly') }}</p></div>
        <a-tag>{{ statusLabel(panel.status) }}</a-tag>
      </div>
      <div class="pulse-tiles">
        <article v-for="tile in summaryTiles" :key="tile.label" class="pulse-tile"><span>{{ tile.label }}</span><strong>{{ tile.value }}</strong><small>{{ tile.meta }}</small></article>
      </div>
    </section>
    <div v-if="panel.metrics.length" class="pulse-metric-grid">
      <article v-for="metric in panel.metrics.slice(0, 6)" :key="metricKey(metric)" class="pulse-metric">
        <small>{{ metricLabel(metric) }}</small>
        <strong>{{ formatMetric(metric.value, metric.unit) }}</strong>
        <a-button v-if="metric.evidenceId" type="link" size="small" @click="$emit('open-evidence', metric.evidenceId)">{{ $t('smartInsights.evidence') }}</a-button>
      </article>
    </div>
    <div v-if="chartCards.length" class="pulse-chart-grid">
      <pulse-trend-chart
        v-for="chart in chartCards"
        :key="chart.key"
        :title="chart.title"
        :series="chart.series"
        :status="chart.status"
        :unit="chart.unit"
      />
    </div>
    <div v-else class="pulse-empty"><a-icon type="database" /><span>{{ $t('smartInsights.noHistory') }}</span></div>
  </section>
</template>

<script>
import { MARKET_PULSE_TABS, buildPulsePanel, pulseTabLabel } from '../marketPulse'
import PulseTrendChart from './PulseTrendChart'

export default {
  name: 'MarketPulseSection',
  components: { PulseTrendChart },
  props: {
    pulse: { type: Object, default: () => ({}) },
    locale: { type: String, default: 'vi' }
  },
  data () { return { tabs: MARKET_PULSE_TABS, activeKey: 'overview' } },
  computed: {
    activeTab () { return this.tabs.find(tab => tab.key === this.activeKey) || this.tabs[0] },
    panel () { return buildPulsePanel(this.pulse, this.activeKey) },
    summaryTiles () {
      return [
        { label: this.$t('smartInsights.metrics'), value: this.panel.metrics.length, meta: this.$t('smartInsights.observations') },
        { label: this.$t('smartInsights.chartSeries'), value: this.panel.seriesGroups.length, meta: this.$t('smartInsights.history') },
        { label: this.$t('smartInsights.verifiedSources'), value: this.panel.sources.length, meta: this.$t('smartInsights.sources') }
      ]
    },
    chartCards () {
      const cards = []
      if (this.activeKey === 'overview' || this.activeKey === 'sentiment') {
        const fear = this.panel.fearGreed
        if (fear) cards.push({ key: 'fear-greed', title: this.$t('smartInsights.fearGreedTitle'), series: fear.series || [], status: fear.status, unit: '' })
      }
      if (this.activeKey === 'overview' || this.activeKey === 'flows') {
        const flow = this.panel.etfFlows
        if (flow) cards.push({ key: 'etf-flow', title: this.$t('smartInsights.flowTitle'), series: flow.series || [], status: flow.status, unit: 'USD' })
      }
      const limit = cards.length ? 4 : 6
      this.panel.seriesGroups.slice(0, limit).forEach(group => {
        cards.push({ key: group.key, title: this.metricLabel({ metric: group.key.split(':')[0] }), series: group.points, status: this.panel.status, unit: '' })
      })
      return cards
    }
  },
  methods: {
    tabLabel (tab) { return pulseTabLabel(tab, this.locale === 'vi-VN' || this.locale === 'vi' ? 'vi' : 'en') },
    statusLabel (status) {
      const labels = {
        AVAILABLE: this.$t('smartInsights.availableStatus'),
        PARTIAL: this.$t('smartInsights.partialStatus'),
        STALE: this.$t('smartInsights.stale'),
        UNAVAILABLE: this.$t('smartInsights.unavailableShort')
      }
      return labels[String(status || 'UNAVAILABLE').toUpperCase()] || this.$t('smartInsights.unavailableShort')
    },
    metricKey (metric) { return `${metric.metric || 'metric'}-${metric.symbol || ''}-${metric.effectiveAt || ''}` },
    metricLabel (metric) {
      const key = String(metric.metric || '').toLowerCase().split('.').pop()
      const labels = {
        fear_greed: this.$t('smartInsights.metricFearGreed'),
        index: this.$t('smartInsights.metricIndex'),
        net_flow_usd: this.$t('smartInsights.metricNetFlow'),
        funding_rate: this.$t('smartInsights.metricFundingRate'),
        open_interest: this.$t('smartInsights.metricOpenInterest'),
        liquidation_usd: this.$t('smartInsights.metricLiquidation'),
        stablecoin_supply_usd: this.$t('smartInsights.metricStablecoinSupply'),
        chain_tvl_usd: this.$t('smartInsights.metricChainTvl'),
        aum_usd: this.$t('smartInsights.metricAum'),
        address_balance_btc: this.$t('smartInsights.metricAddressBalance'),
        balance_change_btc: this.$t('smartInsights.metricBalanceChange'),
        cbbi: this.$t('smartInsights.metricCbbi')
      }
      return labels[key] || (this.$i18n && this.$i18n.locale === 'vi-VN' ? `${this.$t('smartInsights.metricLabel')}: ${key.replace(/[_-]+/gu, ' ')}` : key.replace(/[_-]+/gu, ' '))
    },
    formatMetric (value, unit) {
      const number = Number(value)
      if (!Number.isFinite(number)) return this.$t('smartInsights.dataUnavailableShort')
      return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(number)}${unit ? ` ${unit}` : ''}`
    }
  }
}
</script>

<style lang="less" scoped>
.market-pulse { margin-top: 28px; }
.section-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.section-title-row h2 { margin: 0; color: var(--ink); font-size: 17px; }
.section-title-row h2 .ant-tag { vertical-align: 2px; color: #18a575; border-color: #b7ead6; background: #ecfbf4; }
.section-title-row p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
.pulse-tabs { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 12px; }
.pulse-tabs button { padding: 7px 12px; border: 1px solid var(--line); border-radius: 7px; color: var(--muted); background: var(--card); font-size: 12px; transition: .2s ease; }
.pulse-tabs button.active, .pulse-tabs button:hover { color: var(--blue); border-color: var(--primary-color-ring, var(--blue-ring)); background: var(--soft-blue); }
.pulse-tabs button:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
.pulse-summary { margin-top: 14px; }
.legacy-card { overflow: hidden; border: 1px solid var(--line); border-radius: 12px; background: var(--card); box-shadow: 0 3px 12px var(--blue-ring); }
.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 17px; border-bottom: 1px solid var(--line); background: linear-gradient(var(--soft-blue), var(--card)); }
.compact-heading { padding-top: 13px; padding-bottom: 13px; }
.card-heading h3 { margin: 0; color: var(--ink); font-size: 15px; }
.card-heading p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
.card-heading .ant-tag { margin: 0; font-size: 11px; }
.pulse-tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; padding: 12px 15px 15px; }
.pulse-tile { display: grid; gap: 5px; min-height: 72px; padding: 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--page-bg); }
.pulse-tile span, .pulse-tile small, .pulse-metric small { color: var(--muted); font-size: 11px; }
.pulse-tile strong { color: var(--ink); font-size: 19px; }
.pulse-metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; margin-top: 12px; }
.pulse-metric { display: grid; gap: 6px; padding: 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--card); }
.pulse-metric strong { color: var(--ink); font-size: 18px; font-variant-numeric: tabular-nums; }
.pulse-metric .ant-btn { padding: 0; justify-self: start; font-size: 11px; }
.pulse-chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.pulse-empty { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 160px; margin-top: 12px; color: var(--muted); font-size: 12px; }
@media (max-width: 680px) { .pulse-tiles, .pulse-metric-grid, .pulse-chart-grid { grid-template-columns: 1fr; } }
</style>
