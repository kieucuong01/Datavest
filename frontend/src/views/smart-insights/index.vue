<template>
  <div class="legacy-page" :class="{ 'theme-dark': isDarkTheme }">

    <main class="legacy-main">
      <section class="analysis-controls" :aria-label="$t('smartInsights.analysisControls')">
        <div class="date-control">
          <label>{{ $t('smartInsights.analysisDate') }}</label>
          <a-select
            v-model="asOf"
            allow-clear
            size="small"
            :loading="datesLoading"
            :disabled="datesLoading"
            @change="loadAll">
            <a-select-option v-for="item in dates" :key="item" :value="item">{{ formatDate(item) }}</a-select-option>
          </a-select>
        </div>
        <a-button size="small" @click="showToday">{{ $t('smartInsights.today') }}</a-button>
        <div class="control-spacer" />
      </section>

      <a-alert v-if="errorMessage" class="legacy-alert" type="error" show-icon :message="errorMessage" />

      <section v-if="overviewLoading && !overview" class="initial-overview-loading" aria-busy="true" aria-live="polite">
        <a-skeleton active :paragraph="{ rows: 5 }" />
      </section>
      <template v-else>
        <section class="daily-hero">
          <div class="hero-copy">
            <div class="hero-kicker">
              <span class="hero-badge"><a-icon type="bar-chart" /> {{ $t('smartInsights.legacyHeroBadge') }}</span>
              <span class="hero-status">{{ overviewStatus }}</span>
              <span class="hero-date">{{ analysisDateLabel }}</span>
            </div>
            <h1>{{ $t('smartInsights.legacyHeroTitle') }}</h1>
            <p><span class="hero-arrow">▲</span> {{ dailyBriefSummary }}</p>
            <a-button v-if="dailyBrief.status === 'AVAILABLE'" ghost size="small" class="hero-read-more" @click="heroExpanded = !heroExpanded">
              {{ heroExpanded ? $t('smartInsights.collapse') : $t('smartInsights.readMore') }}
            </a-button>
            <p v-if="heroExpanded && dailyBrief.status === 'AVAILABLE'" class="hero-thesis">{{ dailyBrief.content }}</p>
          </div>
          <button type="button" class="hero-audio" :disabled="dailyBrief.status !== 'AVAILABLE'" @click="toggleHeroSpeech">
            <span class="play-button"><a-icon :type="heroSpeechActive ? 'pause' : 'caret-right'" /></span>
            <span><strong>{{ $t('smartInsights.listenAi') }}</strong><small>{{ heroSpeechActive ? $t('smartInsights.stopListening') : $t('smartInsights.dailyBriefTts') }}</small></span>
          </button>
        </section>

        <section class="legacy-card decision-brief-card" aria-labelledby="decision-brief-title">
          <div class="card-heading">
            <div class="heading-with-icon"><span class="section-icon">✓</span><div><h2 id="decision-brief-title">{{ $t('smartInsights.decisionBrief') }}</h2><p>{{ $t('smartInsights.decisionBriefDesc') }}</p></div></div>
            <a-tag :color="dailyBrief.status === 'UNAVAILABLE' ? 'orange' : 'green'">{{ overviewStatus }}</a-tag>
          </div>
          <div class="brief-facts">
            <div><small>{{ $t('smartInsights.analysisDate') }}</small><strong>{{ analysisDateLabel }}</strong></div>
            <div><small>{{ $t('smartInsights.assets') }}</small><strong>{{ dailyBrief.assetCount || 0 }}</strong></div>
            <div><small>{{ $t('smartInsights.latestAiAnalysis') }}</small><strong>{{ dailyBrief.generatedAt ? formatDateTime(dailyBrief.generatedAt) : $t('smartInsights.notAvailable') }}</strong></div>
            <div><small>{{ $t('smartInsights.checksum') }}</small><code>{{ shortChecksum(dailyBrief.sourceChecksum) }}</code></div>
          </div>
        </section>
      </template>

      <asset-opinions-section
        :rows="opinionRows"
        :loading="opinionsLoading || overviewLoading"
        @refresh="loadAll"
        @open-analysis="openAssetAnalysis"
      />

      <economic-calendar-table
        class="crypto-calendar"
        :events="calendarEvents"
        :filter="calendarFilter"
        :loading="calendarLoading"
        :error="calendarError"
        @filter-change="calendarFilter = $event"
      />

      <market-pulse-section
        :pulse="cryptoPulse || {}"
        :overview="overview || {}"
        :calendar-events="calendarEvents"
        :locale="$i18n && $i18n.locale"
        :loading="pulseLoading"
        @open-evidence="openEvidence"
      />
    </main>

    <footer class="legacy-footer">
      <div class="footer-inner"><div><div class="legacy-brand"><span class="brand-mark">D</span><strong>DataVest</strong></div><p>{{ $t('smartInsights.footerDescription') }}</p></div><div><h3>{{ $t('smartInsights.footerProduct') }}</h3><a href="#" @click.prevent>{{ $t('smartInsights.overviewNav') }}</a><a href="#" @click.prevent>{{ $t('smartInsights.portfolioNav') }}</a><a href="#" @click.prevent>{{ $t('smartInsights.quantRoomNav') }}</a><a href="#" @click.prevent>{{ $t('smartInsights.footerMethodology') }}</a></div></div>
      <div class="footer-bottom"><span>{{ $t('smartInsights.footerDisclaimer') }}</span><span>© {{ new Date().getFullYear() }} Datavest.vn.</span></div>
    </footer>

    <a-modal
      :visible="analysisModalVisible"
      :title="analysisModalTitle"
      :width="760"
      centered
      :footer="null"
      :destroy-on-close="false"
      :mask-closable="true"
      :wrap-class-name="isDarkTheme ? 'asset-analysis-modal theme-dark' : 'asset-analysis-modal'"
      @cancel="closeAssetAnalysis"
    >
      <div v-if="selectedOpinionRow" class="asset-analysis-modal-body" :class="{ 'theme-dark': isDarkTheme }">
        <div class="asset-analysis-header">
          <div>
            <strong>{{ selectedOpinionRow.displaySymbol }}</strong>
            <span>{{ marketLabel(selectedOpinionRow.market) }}</span>
          </div>
          <a-tag :color="selectedOpinionReport ? 'green' : 'orange'">
            {{ selectedOpinionReport ? overviewStatus : $t('smartInsights.dataUnavailableShort') }}
          </a-tag>
        </div>

        <div v-if="selectedOpinionReport" class="asset-analysis-meta">
          <span>{{ $t('smartInsights.analysisDate') }}: {{ analysisDateLabel }}</span>
          <span>{{ $t('smartInsights.lastAiRun') }}: {{ formatDateTime(selectedOpinionReport.createdAt) }}</span>
        </div>

        <section v-if="selectedOpinionReport" class="analysis-drawer-section">
          <div class="analysis-drawer-section-title"><a-icon type="thunderbolt" /><h3>{{ $t('smartInsights.latestAiAnalysis') }}</h3></div>
          <div class="analysis-result-grid">
            <div><small>{{ $t('smartInsights.aiDecision') }}</small><strong>{{ selectedOpinionReport.decision || $t('smartInsights.notAvailable') }}</strong></div>
            <div><small>{{ $t('smartInsights.aiConfidence') }}</small><strong>{{ selectedOpinionReport.confidence != null ? `${selectedOpinionReport.confidence}%` : $t('smartInsights.notAvailable') }}</strong></div>
          </div>
          <div v-if="selectedOpinionReport.summary" class="analysis-copy">
            <h4>{{ $t('smartInsights.aiSummary') }}</h4>
            <p>{{ selectedOpinionReport.summary }}</p>
          </div>
          <div v-if="selectedOpinionReport.reasons && selectedOpinionReport.reasons.length" class="analysis-copy">
            <h4>{{ $t('smartInsights.analysisEvidence') }}</h4>
            <ul><li v-for="(reason, index) in selectedOpinionReport.reasons" :key="index">{{ reason }}</li></ul>
          </div>
        </section>
        <section v-else class="analysis-drawer-section analysis-empty">
          <a-icon type="clock-circle" />
          <p>{{ $t('smartInsights.aiNoResult') }}</p>
          <router-link to="/ai-asset-analysis" @click.native="closeAssetAnalysis">{{ $t('smartInsights.manageWatchlist') }}</router-link>
        </section>
      </div>
    </a-modal>

    <a-drawer
      :visible="evidenceVisible"
      :title="$t('smartInsights.evidence')"
      :width="560"
      :wrap-class-name="isDarkTheme ? 'insights-drawer theme-dark' : 'insights-drawer'"
      @close="evidenceVisible = false"
    >
      <a-spin :spinning="evidenceLoading"><a-descriptions v-if="evidence" bordered :column="1" size="small"><a-descriptions-item :label="$t('smartInsights.provider')">{{ evidence.sourceName || evidence.source }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.sourceUrl')"><a v-if="evidence.sourceUrl" :href="evidence.sourceUrl" target="_blank" rel="noopener">{{ evidence.sourceUrl }}</a><span v-else>—</span></a-descriptions-item><a-descriptions-item :label="$t('smartInsights.observedAt')">{{ evidence.observedAt }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.effectiveAt')">{{ evidence.effectiveAt }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.reliability')">{{ evidence.reliability || '—' }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.dataClass')">{{ evidence.dataClass || '—' }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.methodology')">{{ evidence.methodologyVersion }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.value')"><pre>{{ pretty(evidence.value) }}</pre></a-descriptions-item><a-descriptions-item :label="$t('smartInsights.warnings')">{{ (evidence.warnings || []).join(', ') || $t('smartInsights.none') }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.checksum')"><code>{{ evidence.checksum }}</code></a-descriptions-item></a-descriptions></a-spin>
    </a-drawer>
    <a-drawer
      :visible="healthVisible"
      :title="$t('smartInsights.dataHealth')"
      :width="760"
      :wrap-class-name="isDarkTheme ? 'insights-drawer theme-dark' : 'insights-drawer'"
      @close="healthVisible = false"
    >
      <a-spin :spinning="healthLoading">
        <a-table
          row-key="code"
          size="small"
          :pagination="false"
          :columns="healthColumns"
          :data-source="health"
          :scroll="{ x: 700 }"
        />
      </a-spin>
    </a-drawer>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import { getWatchlist } from '@/api/market'
import { getEconomicCalendar } from '@/api/global-market'
import { getSmartInsightsCryptoPulse, getSmartInsightsDataHealth, getSmartInsightsDates, getSmartInsightsEvidence, getSmartInsightsOverview } from '@/api/smart-insights'
import { runSectionLoaders } from './loadingCoordinator'
import { buildWatchlistOpinionRows } from './watchlistOpinions'
import AssetOpinionsSection from './components/AssetOpinionsSection'
import EconomicCalendarTable from './components/EconomicCalendarTable'
import MarketPulseSection from './components/MarketPulseSection'

export default {
  name: 'SmartInsights',
  components: { AssetOpinionsSection, EconomicCalendarTable, MarketPulseSection },
  data () {
    return {
      asOf: undefined,
      dates: [],
      overview: null,
      cryptoPulse: null,
      calendarEvents: [],
      calendarFilter: {
        timePreset: 'thisWeek',
        countries: ['US', 'VN'],
        impacts: [],
        customStart: '',
        customEnd: ''
      },
      calendarLoading: false,
      calendarError: '',
      health: [],
      watchlist: [],
      evidence: null,
      selectedOpinionRow: null,
      datesLoading: false,
      overviewLoading: false,
      opinionsLoading: false,
      pulseLoading: false,
      healthLoading: false,
      evidenceLoading: false,
      evidenceVisible: false,
      analysisModalVisible: false,
      healthVisible: false,
      heroExpanded: false,
      heroSpeechActive: false,
      errorMessage: ''
    }
  },
  computed: {
    ...mapState({ navTheme: state => state.app.theme }),
    isDarkTheme () { return this.navTheme === 'dark' || this.navTheme === 'realdark' },
    hasOverview () { return Boolean(this.overview && this.overview.status !== 'UNAVAILABLE') },
    dailyBrief () { return (this.overview && this.overview.dailyBrief) || { status: 'UNAVAILABLE', content: '', assetCount: 0 } },
    opinionRows () {
      return buildWatchlistOpinionRows(this.watchlist, this.overview && this.overview.opinions)
    },
    analysisModalTitle () {
      const symbol = this.selectedOpinionRow && this.selectedOpinionRow.displaySymbol
      return symbol ? `${this.$t('smartInsights.viewAnalysis')} · ${symbol}` : this.$t('smartInsights.viewAnalysis')
    },
    selectedOpinionReport () { return this.selectedOpinionRow && this.selectedOpinionRow.report },
    overviewStatus () { return this.statusLabel(this.hasOverview ? this.overview.status : 'UNAVAILABLE') },
    analysisDateLabel () { return this.formatDate(this.asOf || (this.overview && this.overview.asOf) || this.dates[0]) },
    dailyBriefSummary () { return this.dailyBrief.status === 'AVAILABLE' ? this.dailyBrief.content.split('\n')[0] : this.dailyBrief.content || this.$t('smartInsights.aiNoResult') },
    healthColumns () {
      return [
        { title: this.$t('smartInsights.provider'), dataIndex: 'name', width: 180 },
        { title: this.$t('smartInsights.activationMode'), dataIndex: 'activationMode', customRender: value => this.modeLabel(value), width: 130 },
        { title: this.$t('smartInsights.freshness'), dataIndex: 'freshness', customRender: value => this.stateLabel(value), width: 110 },
        { title: this.$t('smartInsights.coverage'), dataIndex: 'coverage.liveObservations30d', width: 150 },
        { title: this.$t('smartInsights.lastRun'), dataIndex: 'lastRun.status', customRender: value => this.lastRunLabel(value), width: 130 },
        { title: this.$t('smartInsights.methodology'), dataIndex: 'methodologyVersion', width: 150 }
      ]
    }
  },
  mounted () {
    this.loadAll()
  },
  methods: {
    async loadAll () {
      this.errorMessage = ''
      const results = await runSectionLoaders({
        dates: this.loadDates,
        overview: this.loadOverview,
        opinions: this.loadWatchlist,
        pulse: this.loadPulse,
        calendar: this.loadCalendar
      }, this.setSectionLoading)
      const failed = results.find(result => result.status === 'rejected')
      if (failed) {
        this.errorMessage = this.friendlyError(failed.reason, 'smartInsights.unavailable')
      }
    },
    async showToday () {
      this.asOf = new Date().toISOString().slice(0, 10)
      await this.loadAll()
    },
    setSectionLoading (section, active) {
      const fields = { dates: 'datesLoading', overview: 'overviewLoading', opinions: 'opinionsLoading', pulse: 'pulseLoading', calendar: 'calendarLoading' }
      if (fields[section]) this[fields[section]] = active
    },
    async loadOverview () {
      const response = await getSmartInsightsOverview({
        as_of: this.asOf,
        lang: (this.$i18n && this.$i18n.locale) || 'en-US'
      })
      this.overview = response.data
    },
    async loadDates () {
      const response = await getSmartInsightsDates()
      this.dates = (response.data && response.data.dates) || []
      if (!this.asOf && this.dates.length) this.asOf = this.dates[0]
    },
    async loadHealth () {
      this.healthLoading = true
      try { const response = await getSmartInsightsDataHealth(); this.health = (response.data && response.data.sources) || [] } finally { this.healthLoading = false }
    },
    async loadPulse () { const response = await getSmartInsightsCryptoPulse({ as_of: this.asOf, compact: 1 }); this.cryptoPulse = response.data },
    async loadCalendar (force = false) {
      this.calendarLoading = true
      this.calendarError = ''
      try {
        const response = await getEconomicCalendar({ force: force ? 1 : undefined, days: 14, lang: (this.$i18n && this.$i18n.locale) || 'en-US' })
        if (!response || response.code !== 1) throw new Error(response && response.msg ? response.msg : this.$t('smartInsights.calendarUnavailable'))
        this.calendarEvents = Array.isArray(response.data) ? response.data : []
        if (!this.calendarEvents.length && response.meta && response.meta.message) this.calendarError = response.meta.message
      } catch (error) {
        this.calendarEvents = []
        this.calendarError = this.friendlyError(error, 'smartInsights.calendarLoadFailed')
      } finally {
        this.calendarLoading = false
      }
    },
    async loadWatchlist () {
      try {
        const response = await getWatchlist()
        const data = response && response.data
        this.watchlist = Array.isArray(data) ? data : ((data && Array.isArray(data.watchlist)) ? data.watchlist : [])
      } catch (error) {
        this.watchlist = []
        this.errorMessage = this.friendlyError(error, 'smartInsights.watchlistUnavailable')
      }
    },
    async openAssetAnalysis (row) {
      this.selectedOpinionRow = row
      this.analysisModalVisible = true
    },
    closeAssetAnalysis () {
      this.analysisModalVisible = false
    },
    toggleHeroSpeech () {
      if (!this.dailyBrief.content || typeof window === 'undefined' || !window.speechSynthesis) return
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel()
        this.heroSpeechActive = false
        return
      }
      const utterance = new window.SpeechSynthesisUtterance(this.dailyBrief.content)
      utterance.lang = this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US'
      utterance.onend = () => { this.heroSpeechActive = false }
      utterance.onerror = () => { this.heroSpeechActive = false }
      this.heroSpeechActive = true
      window.speechSynthesis.speak(utterance)
    },
    async openEvidence (id) {
      this.evidenceVisible = true; this.evidenceLoading = true; this.evidence = null
      try { const response = await getSmartInsightsEvidence(id); this.evidence = response.data } catch (error) { this.errorMessage = this.friendlyError(error, 'smartInsights.unavailable') } finally { this.evidenceLoading = false }
    },
    statusLabel (status) {
      const labels = {
        COMPLETE: this.$t('smartInsights.availableStatus'),
        AVAILABLE: this.$t('smartInsights.availableStatus'),
        PARTIAL: this.$t('smartInsights.partialStatus'),
        LIVE: this.$t('smartInsights.live'),
        STALE: this.$t('smartInsights.stale'),
        UNAVAILABLE: this.$t('smartInsights.unavailableShort'),
        NEVER: this.$t('smartInsights.never')
      }
      return labels[String(status || 'UNAVAILABLE').toUpperCase()] || this.$t('smartInsights.unavailableShort')
    },
    modeLabel (value) { return this.statusLabel(value) },
    stateLabel (value) { return this.statusLabel(value) },
    lastRunLabel (value) { return this.statusLabel(value || 'NE' + 'VER') },
    severityLabel (value) {
      const labels = { high: this.$t('smartInsights.high'), medium: this.$t('smartInsights.medium'), low: this.$t('smartInsights.low'), danger: this.$t('smartInsights.high'), warning: this.$t('smartInsights.medium') }
      return labels[String(value || '').toLowerCase()] || String(value || this.$t('smartInsights.notAvailable'))
    },
    impactLabel (value) {
      const labels = { high: this.$t('smartInsights.high'), medium: this.$t('smartInsights.medium'), low: this.$t('smartInsights.low') }
      return labels[String(value || '').toLowerCase()] || value || this.$t('smartInsights.notAvailable')
    },
    friendlyError (error, key) {
      if (this.$i18n && this.$i18n.locale === 'vi-VN') return this.$t(key)
      return String((error && error.message) || this.$t(key))
    },
    pretty (value) { return JSON.stringify(value || {}, null, 2) },
    shortChecksum (value) { const text = String(value || ''); return text ? `${text.slice(0, 10)}...${text.slice(-6)}` : this.$t('smartInsights.notAvailable') },
    formatDate (value) { if (!value) return this.$t('smartInsights.dataUnavailableShort'); const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString(this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-GB') },
    formatDateTime (value) {
      if (!value) return this.$t('smartInsights.notAvailable')
      const numeric = typeof value === 'number' ? (value < 100000000000 ? value * 1000 : value) : value
      const date = new Date(numeric)
      if (Number.isNaN(date.getTime())) return String(value)
      const locale = this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-GB'
      return date.toLocaleString(locale, { dateStyle: 'short', timeStyle: 'short' })
    },
    marketLabel (value) { const labels = { all: this.$t('smartInsights.all'), crypto: 'Crypto', vn: 'VN', us: 'US', gold: this.$t('smartInsights.gold') }; return labels[value] || String(value || '').toUpperCase() }
  }
}
</script>

<style lang="less" scoped>
.asset-analysis-modal-body { --page-bg: #f7f9fc; --ink: #17253d; --muted: #7b8798; --line: #e4eaf3; --card: #fff; --blue: var(--primary-color, #174ca8); --soft-blue: var(--primary-color-soft, rgba(24,144,255,.1)); max-height: 72vh; padding-right: 4px; overflow-y: auto; color: var(--ink); }
.asset-analysis-modal-body.theme-dark { --page-bg: #111827; --ink: #eef4ff; --muted: #9aa8bc; --line: #2a3547; --card: #182235; --soft-blue: rgba(24,144,255,.16); }
.asset-analysis-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }.asset-analysis-header > div { display: grid; gap: 3px; }.asset-analysis-header strong { color: var(--ink); font-size: 18px; }.asset-analysis-header span { color: var(--muted); font-size: 12px; }
.asset-analysis-meta { display: flex; flex-wrap: wrap; gap: 12px; padding: 10px 0; color: var(--muted); font-size: 12px; }
.analysis-drawer-section { margin-top: 16px; padding: 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--card); }.analysis-drawer-section-title { display: flex; align-items: center; gap: 7px; }.analysis-drawer-section-title .anticon { color: var(--blue); }.analysis-drawer-section-title h3 { margin: 0; color: var(--ink); font-size: 15px; }.analysis-result-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }.analysis-result-grid > div { display: grid; gap: 4px; padding: 9px 10px; border-radius: 8px; background: var(--soft-blue); }.analysis-result-grid small { color: var(--muted); font-size: 11px; }.analysis-result-grid strong { color: var(--ink); font-size: 16px; }.analysis-copy { margin-top: 13px; }.analysis-copy h4 { margin: 0 0 5px; color: var(--ink); font-size: 13px; }.analysis-copy p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.65; white-space: pre-wrap; }.analysis-report { margin-top: 13px; overflow: auto; color: var(--ink); font-size: 13px; line-height: 1.6; }.analysis-report :deep(.qd-report) { max-width: 100%; }
.analysis-evidence-desc { margin: 5px 0 10px; color: var(--muted); font-size: 12px; }.analysis-evidence-list { display: grid; gap: 8px; }.analysis-evidence-item { padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--page-bg); }.analysis-evidence-item-head, .analysis-evidence-item-meta { display: flex; justify-content: space-between; gap: 10px; }.analysis-evidence-item-head strong { color: var(--ink); font-size: 13px; }.analysis-evidence-item-head span, .analysis-evidence-item-meta { color: var(--muted); font-size: 11px; }.analysis-evidence-item-meta { margin-top: 4px; flex-wrap: wrap; }.analysis-evidence-item a { display: block; overflow: hidden; margin-top: 7px; color: var(--blue); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.analysis-evidence-item pre { max-height: 150px; margin: 8px 0 0; padding: 8px; overflow: auto; border-radius: 6px; color: var(--ink); background: var(--card); font-size: 11px; white-space: pre-wrap; word-break: break-word; }.analysis-empty { display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 7px; min-height: 90px; color: var(--muted); text-align: center; }.analysis-empty p { margin: 0; font-size: 13px; }.analysis-empty a { color: var(--blue); font-size: 13px; }.analysis-empty--compact { min-height: 48px; }
.legacy-page { --page-bg: #f7f9fc; --ink: #17253d; --muted: #7b8798; --line: #e4eaf3; --card: #fff; --blue: var(--primary-color, #174ca8); --blue-hover: var(--primary-color-hover, #40a9ff); --blue-active: var(--primary-color-active, #096dd9); --blue-ring: var(--primary-color-ring, rgba(24,144,255,.22)); --soft-blue: var(--primary-color-soft, rgba(24,144,255,.1)); --soft-blue-strong: var(--primary-color-soft-strong, rgba(24,144,255,.18)); position: relative; min-height: calc(100vh - 64px); overflow: hidden; color: var(--ink); background: var(--page-bg); font-size: 15px; }
.legacy-main, .footer-inner, .footer-bottom { width: 100%; max-width: 1120px; margin: 0 auto; }
.legacy-main { width: 100%; max-width: 1480px; margin: 0 auto; box-sizing: border-box; padding: 24px 28px 48px; }.analysis-controls { display: flex; align-items: end; gap: 10px; min-height: 40px; margin-bottom: 17px; }.date-control { display: grid; grid-template-columns: auto 130px; align-items: center; gap: 8px; }.date-control label { color: var(--muted); font-size: 13px; font-weight: 600; }.date-control .ant-select { width: 130px; }.analysis-controls .ant-btn, .analysis-controls .ant-radio-button-wrapper, .date-control .ant-select-selection-selected-value { font-size: 13px; }.control-spacer { flex: 1; }.legacy-alert { margin-bottom: 12px; }.initial-overview-loading { min-height: 184px; padding: 34px 38px; border: 1px solid var(--line); border-radius: 17px; background: var(--card); box-shadow: 0 8px 24px var(--blue-ring); }
.daily-hero { display: flex; align-items: center; justify-content: space-between; min-height: 184px; padding: 30px 38px; overflow: hidden; border-radius: 17px; color: #fff; background: linear-gradient(115deg, var(--blue-active) 0%, var(--blue) 52%, var(--blue-hover) 122%); box-shadow: 0 14px 28px var(--blue-ring); }.hero-copy { position: relative; z-index: 1; min-width: 0; }.hero-kicker { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; color: rgba(255,255,255,.78); font-size: 12px; }.hero-badge, .hero-status { padding: 4px 9px; border: 1px solid rgba(255,255,255,.2); border-radius: 999px; background: rgba(255,255,255,.12); }.hero-badge { font-weight: 700; }.daily-hero h1 { max-width: 620px; margin: 0 0 9px; color: #fff; font-size: clamp(30px, 4vw, 42px); line-height: 1.08; letter-spacing: -.04em; }.daily-hero p { margin: 0; color: rgba(255,255,255,.82); font-size: 13px; }.hero-thesis { margin-top: 6px !important; color: rgba(255,255,255,.62) !important; }.hero-arrow { color: var(--blue-hover); }.hero-audio { display: flex; align-items: center; gap: 12px; min-width: 190px; padding: 11px 15px; border: 1px solid rgba(255,255,255,.18); border-radius: 12px; color: #fff; text-align: left; background: rgba(255,255,255,.1); opacity: .7; }.hero-audio strong, .hero-audio small { display: block; }.hero-audio strong { font-size: 13px; }.hero-audio small { margin-top: 3px; color: rgba(255,255,255,.62); font-size: 11px; }.play-button { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%; color: var(--blue); background: rgba(255,255,255,.75); }
.legacy-card { margin-top: 16px; overflow: hidden; border: 1px solid var(--line); border-radius: 12px; background: var(--card); box-shadow: 0 3px 12px var(--blue-ring); }.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 17px; border-bottom: 1px solid var(--line); background: linear-gradient(var(--soft-blue), var(--card)); }.heading-with-icon { display: flex; align-items: flex-start; gap: 9px; min-width: 0; }.section-icon { display: inline-grid; place-items: center; flex: 0 0 auto; width: 30px; height: 30px; border-radius: 8px; color: #fff; background: var(--blue); font-size: 17px; font-weight: 700; }.card-heading h2 { margin: 0; color: var(--ink); font-size: 16px; line-height: 1.3; }.card-heading p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }.card-heading h2 .ant-tag { vertical-align: 2px; color: #18a575; border-color: #b7ead6; background: #ecfbf4; }
.change-list { width: 100%; }.change-row { display: grid; grid-template-columns: 1.1fr 1fr 20px; align-items: center; gap: 12px; min-height: 52px; padding: 10px 16px; border-bottom: 1px solid var(--line); }.change-row:last-child { border-bottom: 0; }.change-row > div:first-child { display: grid; gap: 2px; }.change-row strong { font-size: 13px; }.change-row span, .change-row small { color: var(--muted); font-size: 12px; }.change-detail { display: flex; justify-content: space-between; gap: 10px; }.legacy-empty { display: flex; align-items: center; justify-content: center; gap: 9px; color: var(--muted); text-align: center; }.legacy-empty div { display: grid; gap: 4px; text-align: left; }.legacy-empty span, .legacy-empty strong { font-size: 13px; }.calendar-empty { min-height: 120px; flex-direction: column; }
.brief-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; padding: 1px; background: var(--line); }.brief-facts > div { display: grid; gap: 5px; min-height: 72px; padding: 14px 16px; background: var(--card); }.brief-facts small { color: var(--muted); font-size: 11px; }.brief-facts strong, .brief-facts code { color: var(--ink); font-size: 14px; font-variant-numeric: tabular-nums; }.brief-facts code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.risk-alerts { display: grid; gap: 8px; margin-top: 12px; }.risk-alerts .ant-alert { border-radius: 9px; }.crypto-calendar { margin-top: 18px; }.calendar-filters { display: flex; gap: 4px; }.calendar-filters .ant-btn { padding: 0 9px; font-size: 12px; }
.legacy-footer { margin-top: 22px; border-top: 1px solid var(--line); background: var(--card); }.footer-inner { display: grid; grid-template-columns: 1.5fr 1fr; gap: 24px; padding: 36px 0 30px; }.legacy-brand { display: inline-flex; align-items: center; gap: 6px; color: var(--ink); white-space: nowrap; }.brand-mark { display: inline-grid; place-items: center; width: 25px; height: 25px; border-radius: 6px; color: #fff; background: var(--blue); font-size: 14px; font-weight: 800; }.footer-inner p { max-width: 320px; margin: 10px 0 0; color: var(--muted); font-size: 12px; line-height: 1.7; }.footer-inner > div:last-child { display: grid; align-content: start; gap: 6px; justify-self: end; min-width: 150px; }.footer-inner h3 { margin: 0 0 3px; color: var(--muted); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }.footer-inner a { color: var(--muted); font-size: 12px; text-decoration: none; }.footer-bottom { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-top: 1px solid var(--line); color: var(--muted); font-size: 11px; }.footer-bottom span:first-child { max-width: 720px; }.demo-watermark { position: fixed; right: 4vw; bottom: 8vh; z-index: 0; color: rgba(190,110,10,.08); font-size: 15vw; font-weight: 800; transform: rotate(-12deg); pointer-events: none; }
.theme-dark { --page-bg: #0c1118; --ink: #e9eff7; --muted: #9ba9ba; --line: #263341; --card: #121a23; --soft-blue: var(--primary-color-soft-strong, rgba(24,144,255,.18)); --soft-blue-strong: var(--primary-color-soft-strong, rgba(24,144,255,.18)); }.theme-dark .legacy-footer { background: var(--card); }.theme-dark .card-heading { background: linear-gradient(var(--soft-blue), var(--card)); }.theme-dark .change-row { border-color: var(--line); }.theme-dark .footer-inner a { color: var(--muted); }
@media (max-width: 960px) { .legacy-main { width: 100%; }.analysis-controls { flex-wrap: wrap; align-items: stretch; }.control-spacer { display: none; }.date-control { flex: 1 1 100%; grid-template-columns: auto 118px; } }
@media (max-width: 680px) { .legacy-main { padding: 14px 12px 32px; }.date-control { grid-template-columns: auto 1fr; }.date-control .ant-select { width: 100%; }.daily-hero { align-items: flex-start; flex-direction: column; gap: 22px; padding: 25px 22px; }.daily-hero h1 { font-size: 32px; }.hero-audio { width: 100%; }.card-heading { align-items: flex-start; flex-direction: column; }.calendar-filters { flex-wrap: wrap; }.analysis-result-grid { grid-template-columns: 1fr; }.footer-inner { width: calc(100% - 24px); grid-template-columns: 1fr; }.footer-inner > div:last-child { justify-self: start; }.footer-bottom { width: calc(100% - 24px); flex-direction: column; } }
</style>

<style lang="less">
.asset-analysis-modal .ant-modal { max-width: calc(100vw - 24px); }
.asset-analysis-modal .ant-modal-content { overflow: hidden; border-radius: 14px; box-shadow: 0 20px 60px rgba(12, 28, 52, .22); }
.asset-analysis-modal .ant-modal-header { padding: 16px 20px; border-bottom-color: #e4eaf3; }
.asset-analysis-modal .ant-modal-body { padding: 18px 20px 20px; }
.asset-analysis-modal.theme-dark .ant-modal-content, .asset-analysis-modal.theme-dark .ant-modal-header { color: #eef4ff; border-color: #2a3547; background: #182235; }
.asset-analysis-modal.theme-dark .ant-modal-title, .asset-analysis-modal.theme-dark .ant-modal-close { color: #eef4ff; }
@media (max-width: 680px) { .asset-analysis-modal .ant-modal { margin: 12px auto; }.asset-analysis-modal .ant-modal-header { padding: 14px 16px; }.asset-analysis-modal .ant-modal-body { padding: 14px 12px 16px; } }
</style>
