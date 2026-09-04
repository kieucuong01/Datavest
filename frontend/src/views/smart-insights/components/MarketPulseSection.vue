<template>
  <section class="market-pulse" aria-labelledby="market-pulse-title" :aria-busy="loading ? 'true' : 'false'">
    <div class="section-title-row">
      <div>
        <h2 id="market-pulse-title">{{ $t('smartInsights.marketRhythm') }} <a-tag v-if="pulseIsCurrent">{{ $t('smartInsights.currentData') }}</a-tag></h2>
        <p>{{ $t('smartInsights.marketRhythmDesc') }}</p>
      </div>
      <a-tag :color="pulse.status === 'AVAILABLE' ? 'green' : 'orange'">{{ statusLabel(pulse.status) }}</a-tag>
    </div>
    <div v-if="loading" class="pulse-loading" aria-live="polite">
      <a-skeleton active :paragraph="{ rows: 8 }" />
    </div>
    <template v-else>
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
      <section v-if="activeKey === 'macro'" class="legacy-card pulse-summary">
        <div class="card-heading compact-heading">
          <div><h3>{{ tabLabel(activeTab) }}</h3><p>{{ $t('smartInsights.macroPulseDesc') }}</p></div>
          <a-tag :color="calendarEvents.length ? 'green' : 'orange'">{{ calendarEvents.length ? $t('smartInsights.availableStatus') : $t('smartInsights.unavailableShort') }}</a-tag>
        </div>
        <div class="pulse-tiles">
          <article v-for="tile in macroTiles" :key="tile.label" class="pulse-tile"><span>{{ tile.label }}</span><strong>{{ tile.value }}</strong><small>{{ tile.meta }}</small></article>
        </div>
      </section>
      <section v-else-if="activeKey === 'equities'" class="legacy-card pulse-summary">
        <div class="card-heading compact-heading">
          <div><h3>{{ tabLabel(activeTab) }}</h3><p>{{ $t('smartInsights.equitiesPulseDesc') }}</p></div>
          <a-tag :color="equityReportCount ? 'green' : 'orange'">{{ equityReportCount ? $t('smartInsights.availableStatus') : $t('smartInsights.unavailableShort') }}</a-tag>
        </div>
        <div class="pulse-tiles">
          <article class="pulse-tile"><span>VNINDEX · VN30</span><strong>{{ $t('smartInsights.liveDataSources') }}</strong><small>{{ $t('smartInsights.equitiesTickerHint') }}</small></article>
          <article class="pulse-tile"><span>{{ $t('smartInsights.equitiesWatchlist') }}</span><strong>{{ equityReportCount }}</strong><small>{{ $t('smartInsights.latestAiAnalysis') }}</small></article>
          <article class="pulse-tile"><span>{{ $t('smartInsights.analysisDate') }}</span><strong>{{ analysisDate }}</strong><small>{{ $t('smartInsights.equitiesSourceHint') }}</small></article>
        </div>
      </section>
      <template v-else-if="activeKey === 'crypto' && !cryptoReady">
        <div class="crypto-terminal-deferred" aria-live="polite">
          <a-skeleton active :paragraph="{ rows: 8 }" />
        </div>
      </template>
      <template v-else>
        <fear-greed-panel v-if="fearGreed" :fear="fearGreed" />
        <div class="pulse-detail-grid">
          <flow-terminal v-if="panel.etfFlows" :flow="panel.etfFlows" :is-current="pulseIsCurrent" />
          <whale-flow-monitor v-if="panel.whaleFlows" :whale-flow="panel.whaleFlows" />
          <derivatives-terminal :derivatives="panel" />
          <cycle-terminal :cycle="panel" :is-current="pulseIsCurrent" />
          <onchain-terminal :onchain="panel" />
        </div>
      </template>
    </template>
  </section>
</template>

<script>
import { MARKET_PULSE_TABS, buildPulsePanel, pulseTabLabel } from '../marketPulse'
const FearGreedPanel = () => import('./FearGreedPanel')
const FlowTerminal = () => import('./FlowTerminal')
const CycleTerminal = () => import('./CycleTerminal')
const OnchainTerminal = () => import('./OnchainTerminal')
const DerivativesTerminal = () => import('./DerivativesTerminal')
const WhaleFlowMonitor = () => import('./WhaleFlowMonitor')

export default {
  name: 'MarketPulseSection',
  components: { FearGreedPanel, FlowTerminal, CycleTerminal, OnchainTerminal, DerivativesTerminal, WhaleFlowMonitor },
  props: {
    pulse: { type: Object, default: () => ({}) },
    overview: { type: Object, default: () => ({}) },
    calendarEvents: { type: Array, default: () => [] },
    locale: { type: String, default: 'vi' },
    loading: { type: Boolean, default: false },
    cryptoReady: { type: Boolean, default: false }
  },
  data () { return { tabs: MARKET_PULSE_TABS, activeKey: 'crypto' } },
  computed: {
    activeTab () { return this.tabs.find(tab => tab.key === this.activeKey) || this.tabs[0] },
    panel () { return buildPulsePanel(this.pulse, this.activeKey) },
    pulseIsCurrent () { return String(this.pulse && this.pulse.freshness || '').toUpperCase() === 'FRESH' },
    fearGreed () {
      if (this.activeKey !== 'crypto') return null
      const fear = this.panel.fearGreed
      return fear && Array.isArray(fear.series) && fear.series.length ? fear : null
    },
    macroTiles () {
      const events = this.calendarEvents || []
      const highImpact = events.filter(event => String(event && (event.impact || event.importance) || '').toLowerCase() === 'high').length
      const next = events[0] || {}
      return [
        { label: this.$t('smartInsights.macroUpcomingEvents'), value: events.length, meta: next.name || next.event || this.$t('smartInsights.dataUnavailableShort') },
        { label: this.$t('smartInsights.macroHighImpact'), value: highImpact, meta: this.$t('smartInsights.macroCalendarHint') },
        { label: this.$t('smartInsights.verifiedSources'), value: events.length ? 1 : 0, meta: this.$t('smartInsights.macroCalendarHint') }
      ]
    },
    equityReportCount () {
      return Array.isArray(this.overview && this.overview.opinions)
        ? this.overview.opinions.filter(item => String(item && item.market || '').toLowerCase() === 'vn' && item.report).length
        : 0
    },
    analysisDate () { return String((this.overview && this.overview.asOf) || '—') }
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
    }
  }
}
</script>

<style lang="less" scoped>
.market-pulse { margin-top: 28px; }
.pulse-loading { min-height: 320px; margin-top: 12px; padding: 22px; border: 1px solid var(--line); border-radius: 12px; background: var(--card); }
.section-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.section-title-row h2 { margin: 0; color: var(--ink); font-size: 19px; }
.section-title-row h2 .ant-tag { vertical-align: 2px; color: #18a575; border-color: #b7ead6; background: #ecfbf4; }
.section-title-row p { margin: 4px 0 0; color: var(--muted); font-size: 14px; }
.pulse-tabs { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 12px; }
.pulse-tabs button { min-height: 36px; padding: 7px 13px; border: 1px solid var(--line); border-radius: 7px; color: var(--muted); background: var(--card); font-size: 14px; transition: .2s ease; }
.pulse-tabs button.active, .pulse-tabs button:hover { color: var(--blue); border-color: var(--primary-color-ring, var(--blue-ring)); background: var(--soft-blue); }
.pulse-tabs button:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
.pulse-summary { margin-top: 14px; }
.legacy-card { overflow: hidden; border: 1px solid var(--line); border-radius: 12px; background: var(--card); box-shadow: 0 3px 12px var(--blue-ring); }
.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 17px; border-bottom: 1px solid var(--line); background: linear-gradient(var(--soft-blue), var(--card)); }
.compact-heading { padding-top: 13px; padding-bottom: 13px; }
.card-heading h3 { margin: 0; color: var(--ink); font-size: 17px; }
.card-heading p { margin: 3px 0 0; color: var(--muted); font-size: 13px; }
.card-heading .ant-tag { margin: 0; font-size: 11px; }
.pulse-tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; padding: 12px 15px 15px; }
.pulse-tile { display: grid; gap: 5px; min-height: 72px; padding: 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--page-bg); }
.pulse-tile span, .pulse-tile small { color: var(--muted); font-size: 13px; }
.pulse-tile strong { color: var(--ink); font-size: 21px; }
.pulse-detail-grid { display: grid; gap: 12px; margin-top: 12px; }
.crypto-terminal-deferred { min-height: 520px; margin-top: 12px; padding: 22px; border: 1px solid var(--line); border-radius: 12px; background: var(--card); }
@media (max-width: 680px) { .pulse-tiles { grid-template-columns: 1fr; } }
</style>
