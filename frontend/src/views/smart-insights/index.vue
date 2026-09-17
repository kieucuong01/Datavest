<template>
  <div class="legacy-page" :class="{ 'theme-dark': isDarkTheme }">

    <main class="legacy-main">
      <a-alert v-if="errorMessage" class="legacy-alert" type="error" show-icon :message="errorMessage" />

      <section v-if="overviewLoading && !overview" class="initial-overview-loading" aria-busy="true" aria-live="polite">
        <a-skeleton active :paragraph="{ rows: 5 }" />
      </section>
      <asset-opinions-section
        :rows="opinionRows"
        :loading="opinionsLoading || overviewLoading"
        :guest="isGuest"
        @refresh="retrySection('opinions')"
        @open-deep-analysis="openDeepAnalysis"
      />

      <economic-calendar-table
        class="crypto-calendar"
        :events="calendarEvents"
        :filter="calendarFilter"
        :loading="calendarLoading"
        :error="calendarError"
        :meta="calendarMeta"
        @refresh="retrySection('calendar')"
        @filter-change="calendarFilter = $event"
      />

      <market-pulse-section
        :pulse="cryptoPulse || {}"
        :onchain-pulse="cryptoOnchainPulse || {}"
        :overview="overview || {}"
        :calendar-events="calendarEvents"
        :locale="$i18n && $i18n.locale"
        :loading="pulseLoading"
        :detail-loading="pulseDetailsLoading"
        :onchain-loading="pulseOnchainLoading"
        :core-ready="pulseCoreReady"
        @open-evidence="openEvidence"
      />

    </main>

    <footer class="legacy-footer">
      <div class="footer-inner"><div><div class="legacy-brand"><span class="brand-mark">D</span><strong>DataVest</strong></div><p>{{ $t('smartInsights.footerDescription') }}</p></div><div><h3>{{ $t('smartInsights.footerProduct') }}</h3><a href="#" @click.prevent>{{ $t('smartInsights.overviewNav') }}</a><a href="#" @click.prevent>{{ $t('smartInsights.portfolioNav') }}</a><a href="#" @click.prevent>{{ $t('smartInsights.quantRoomNav') }}</a><a href="#" @click.prevent>{{ $t('smartInsights.footerMethodology') }}</a></div></div>
      <div class="footer-bottom"><span>{{ $t('smartInsights.footerDisclaimer') }}</span><span>© {{ new Date().getFullYear() }} Datavest.vn.</span></div>
    </footer>

    <a-modal
      v-if="isGuest"
      :visible="analysisModalVisible"
      :title="analysisModalTitle"
      :width="1152"
      centered
      :footer="null"
      :destroy-on-close="false"
      :mask-closable="true"
      :z-index="1300"
      :wrap-class-name="isDarkTheme ? 'asset-analysis-modal asset-analysis-modal--hub theme-dark' : 'asset-analysis-modal asset-analysis-modal--hub'"
      @cancel="closeAssetAnalysis"
    >
      <div v-if="selectedOpinionRow" class="asset-analysis-modal-body" :class="{ 'theme-dark': isDarkTheme }">
        <div class="asset-analysis-header">
          <div>
            <strong>{{ selectedOpinionRow.displaySymbol }}</strong>
            <span>{{ marketLabel(selectedOpinionRow.market) }}</span>
          </div>
          <a-tag color="blue">TradingAgents</a-tag>
        </div>

        <template>
          <div class="analysis-deep-intro">
            <div>
              <strong>{{ $t('smartInsights.deepAnalysis') }}</strong>
              <span>{{ $t('smartInsights.deepEngine') }}</span>
            </div>
            <a-tag color="blue">TradingAgents</a-tag>
          </div>
          <a-spin :spinning="publicDeepLoading">
            <section v-if="publicDeepReport && publicDeepReport.body" class="analysis-drawer-section public-deep-report">
              <div class="analysis-drawer-section-title"><a-icon type="file-text" /><h3>{{ publicDeepReport.title || $t('smartInsights.deepAnalysis') }}</h3></div>
              <small>{{ publicDeepReport.effectiveDate ? formatDate(publicDeepReport.effectiveDate) : $t('smartInsights.notAvailable') }}</small>
              <div class="public-report-view-switcher">
                <a-radio-group v-model="publicDeepReportView" button-style="solid" size="small" :aria-label="$t('tradingAgents.reportViewLabel')">
                  <a-radio-button value="summary">{{ $t('tradingAgents.summaryView') }}</a-radio-button>
                  <a-radio-button value="full">{{ $t('tradingAgents.fullView') }}</a-radio-button>
                </a-radio-group>
                <span>{{ $t(publicDeepReportView === 'summary' ? 'tradingAgents.summaryViewHint' : 'tradingAgents.fullViewHint') }}</span>
              </div>
              <report-pdf-reader
                :public-asset-key="isGuest ? selectedOpinionRow.publicAssetKey : ''"
                :shared-asset-key="!isGuest ? selectedOpinionRow.sharedResearchAssetKey : ''"
                :variant="publicDeepReportView"
                :pdf-revision="publicDeepPdfRevision"
                :active="analysisModalVisible && analysisMode === 'deep'"
              />
            </section>
            <div v-else class="analysis-empty analysis-empty--compact"><span>{{ publicDeepError || $t('smartInsights.aiReportUnavailable') }}</span></div>
          </a-spin>
        </template>
      </div>
    </a-modal>

    <deep-analysis-panel
      v-else
      :visible="analysisModalVisible"
      :target="deepAnalysisTarget"
      :dark="isDarkTheme"
      @close="closeAssetAnalysis"
    />

    <a-drawer
      :visible="evidenceVisible"
      :title="$t('smartInsights.evidence')"
      :width="560"
      :wrap-class-name="isDarkTheme ? 'insights-drawer theme-dark' : 'insights-drawer'"
      @close="closeEvidence"
    >
      <a-spin :spinning="evidenceLoading"><a-descriptions v-if="evidence" bordered :column="1" size="small"><a-descriptions-item :label="$t('smartInsights.provider')">{{ evidence.sourceName || evidence.source }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.sourceUrl')"><a v-if="evidence.sourceUrl" :href="evidence.sourceUrl" target="_blank" rel="noopener">{{ evidence.sourceUrl }}</a><span v-else>—</span></a-descriptions-item><a-descriptions-item :label="$t('smartInsights.observedAt')">{{ evidence.observedAt }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.effectiveAt')">{{ evidence.effectiveAt }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.reliability')">{{ evidence.reliability || '—' }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.dataClass')">{{ evidence.dataClass || '—' }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.methodology')">{{ evidence.methodologyVersion }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.value')"><pre>{{ pretty(evidence.value) }}</pre></a-descriptions-item><a-descriptions-item :label="$t('smartInsights.warnings')">{{ (evidence.warnings || []).join(', ') || $t('smartInsights.none') }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.checksum')"><code>{{ evidence.checksum }}</code></a-descriptions-item></a-descriptions></a-spin>
    </a-drawer>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import storage from 'store'
import { ACCESS_TOKEN } from '@/store/mutation-types'
import { hasAccessToken } from '@/utils/guestAccess'
import { openAuthModal } from '@/utils/authModal'
import { getEconomicCalendar } from '@/api/global-market'
import { calendarCacheFresh } from './calendarRefresh'
import { getPublicResearchReport, getSharedResearchReports, getSmartInsightsCryptoPulse, getSmartInsightsDates, getSmartInsightsEvidence, getSmartInsightsOverview } from '@/api/smart-insights'
import { getTradingAgentsArtifact, getTradingAgentsRuns } from '@/api/trading-agents'
import { runSectionLoaders } from './loadingCoordinator'
import { formatVietnamDate, formatVietnamDateTime } from '@/utils/vietnamTime'
import { applyAccountDeepReports, applyPublicDeepReports, applySharedResearchStates, buildAccountOpinionRows, buildSharedOpinionRows, opinionAssetKey } from './watchlistOpinions'
import AssetOpinionsSection from './components/AssetOpinionsSection'
import EconomicCalendarTable from './components/EconomicCalendarTable'
import MarketPulseSection from './components/MarketPulseSection'
import DeepAnalysisPanel from '@/components/TradingAgents/DeepAnalysisPanel'
import ReportPdfReader from '@/components/TradingAgents/ReportPdfReader'

function isCurrentRequestToken (requestId, activeRequestId) {
  return requestId === activeRequestId
}

export default {
  name: 'SmartInsights',
  components: { AssetOpinionsSection, EconomicCalendarTable, MarketPulseSection, DeepAnalysisPanel, ReportPdfReader },
  data () {
    return {
      asOf: undefined,
      dates: [],
      overview: null,
      cryptoPulse: null,
      cryptoOnchainPulse: null,
      calendarEvents: [],
      calendarMeta: {},
      calendarFilter: {
        timePreset: 'thisWeek',
        countries: ['US', 'VN'],
        impacts: ['high'],
        customStart: '',
        customEnd: ''
      },
      calendarLoading: false,
      calendarError: '',
      watchlist: [],
      evidence: null,
      selectedOpinionRow: null,
      publicDeepReports: [],
      sharedResearchStates: [],
      accountDeepReports: [],
      publicDeepReport: null,
      publicDeepReportView: 'full',
      publicDeepPdfRevision: 0,
      publicDeepLoading: false,
      publicDeepError: '',
      publicDeepRequestId: 0,
      sharedReportPollingTimer: null,
      sharedReportPollingInFlight: false,
      datesLoading: false,
      overviewLoading: false,
      opinionsLoading: false,
      pulseLoading: false,
      pulseDetailsLoading: false,
      pulseOnchainLoading: false,
      evidenceLoading: false,
      evidenceVisible: false,
      analysisModalVisible: false,
      analysisMode: 'deep',
      deepAnalysisVisible: false,
      deepAnalysisTarget: null,
      requestSequence: 0,
      sectionRequests: {},
      sectionErrors: { overview: false, opinions: false, pulse: false, calendar: false },
      evidenceSequence: 0,
      speechSupported: typeof window !== 'undefined' && Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance),
      smartInsightsCache: {
        dates: null,
        calendar: null,
        overview: new Map(),
        pulse: new Map(),
        pulseCore: new Map(),
        pulseOnchain: new Map()
      },
      retryingSection: '',
      heroExpanded: false,
      heroSpeechActive: false,
      errorMessage: ''
    }
  },
  computed: {
    ...mapState({ navTheme: state => state.app.theme, authToken: state => state.user && state.user.token }),
    isGuest () { return !hasAccessToken(this.authToken || storage.get(ACCESS_TOKEN)) },
    isDarkTheme () { return this.navTheme === 'dark' || this.navTheme === 'realdark' },
    pulseCoreReady () { return Boolean(this.cryptoPulse && this.cryptoPulse.loadStage && this.cryptoPulse.loadStage !== 'summary') },
    hasOverview () { return Boolean(this.overview && this.overview.status !== 'UNAVAILABLE') },
    dailyBrief () { return (this.overview && this.overview.dailyBrief) || { status: 'UNAVAILABLE', content: '', assetCount: 0 } },
    opinionRows () {
      const opinions = this.overview && this.overview.opinions
      const asOf = this.overview && this.overview.asOf
      return this.isGuest
        ? applyPublicDeepReports(buildSharedOpinionRows(this.overview && this.overview.assets, opinions, asOf), this.publicDeepReports)
        : applyAccountDeepReports(
          applySharedResearchStates(buildAccountOpinionRows(this.watchlist, opinions, asOf), this.sharedResearchStates),
          this.accountDeepReports
        )
    },
    dailyBriefHighlights () {
      const highlights = Array.isArray(this.dailyBrief.highlights) ? this.dailyBrief.highlights : []
      if (highlights.length) return highlights.slice(0, 5)
      return this.opinionRows
        .filter(row => row.report)
        .slice(0, 5)
        .map(row => ({
          assetKey: row.id,
          market: row.market,
          symbol: row.symbol,
          displaySymbol: row.displaySymbol,
          decision: row.report.decision || 'HOLD',
          confidence: row.report.confidence,
          summary: row.report.summary || this.$t('smartInsights.aiNoResult'),
          sourceAnalysisId: row.report.id
        }))
    },
    analysisModalTitle () {
      const symbol = this.selectedOpinionRow && this.selectedOpinionRow.displaySymbol
      const modeLabel = this.$t('smartInsights.deepAnalysis')
      return symbol ? `${modeLabel} · ${symbol}` : modeLabel
    },
    overviewStatus () { return this.statusLabel(this.hasOverview ? this.overview.status : 'UNAVAILABLE') }
  },
  watch: {
    '$i18n.locale' () { this.loadAll(false) },
    isGuest (guest, previous) {
      if (guest === previous) return
      this.asOf = undefined
      this.dates = []
      this.watchlist = []
      this.publicDeepReports = []
      this.sharedResearchStates = []
      this.accountDeepReports = []
      this.stopSharedReportPolling()
      this.overview = null
      this.smartInsightsCache.dates = null
      this.smartInsightsCache.overview.clear()
      this.loadAll(true)
    }
  },
  mounted () {
    this.loadAll()
    this.calendarRefreshTimer = window.setInterval(() => {
      if (!document.hidden && !this.calendarLoading && !calendarCacheFresh(this.smartInsightsCache.calendar)) this.retrySection('calendar')
    }, 60000)
  },
  beforeDestroy () {
    window.clearInterval(this.calendarRefreshTimer)
    this.stopSharedReportPolling()
    this.requestSequence++
    this.closeEvidence()
    this.stopHeroSpeech()
  },
  methods: {
    isCurrentRequest (requestId) {
      if (requestId && typeof requestId === 'object') {
        return requestId.page === this.requestSequence && this.sectionRequests[requestId.section] === requestId
      }
      return isCurrentRequestToken(requestId, this.requestSequence)
    },
    runSections (loaders, pageId) {
      const tasks = {}
      Object.entries(loaders).forEach(([section, loader]) => {
        const token = { page: pageId, section }
        this.sectionRequests[section] = token
        tasks[section] = async () => {
          this.setSectionLoading(section, true, token)
          this.sectionErrors[section] = false
          try {
            return await loader(token)
          } catch (error) {
            if (!this.isCurrentRequest(token)) return
            this.sectionErrors[section] = true
            throw error
          } finally { this.setSectionLoading(section, false, token) }
        }
      })
      return runSectionLoaders(tasks)
    },
    cacheKey (asOf = this.asOf) {
      const lang = (this.$i18n && this.$i18n.locale) || 'en-US'
      return `${String(asOf || '')}|${lang}`
    },
    async loadAll (force = false) {
      const requestId = ++this.requestSequence
      this.stopHeroSpeech()
      this.closeAssetAnalysis()
      this.closeEvidence()
      this.heroExpanded = false
      this.retryingSection = ''
      this.overview = null
      this.cryptoPulse = null
      this.cryptoOnchainPulse = null
      this.accountDeepReports = []
      this.pulseDetailsLoading = false
      this.pulseOnchainLoading = false
      this.calendarEvents = []
      this.calendarMeta = {}
      this.calendarError = ''
      ;['dates', 'overview', 'opinions', 'pulse', 'calendar'].forEach(section => this.setSectionLoading(section, false, requestId))
      this.errorMessage = ''
      const independentLoaders = {}
      independentLoaders.opinions = requestId => this.isGuest ? this.loadPublicDeepReports(requestId) : this.loadSharedResearchReports(requestId)
      const independentResults = this.runSections(independentLoaders, requestId)
      const needsDates = force || !Array.isArray(this.smartInsightsCache.dates)
      let datesPending = Promise.resolve()
      if (needsDates) {
        this.setSectionLoading('dates', true, requestId)
        datesPending = this.loadDates(requestId, force).catch(error => {
          if (this.isCurrentRequest(requestId)) this.errorMessage = this.friendlyError(error, 'smartInsights.unavailable')
        }).finally(() => {
          this.setSectionLoading('dates', false, requestId)
        })
      } else {
        this.dates = this.smartInsightsCache.dates
        if (!this.asOf && this.dates.length) this.asOf = this.dates[0]
      }
      if (!this.isCurrentRequest(requestId)) return
      const loaders = {
        overview: requestId => this.loadOverview(requestId, force),
        pulse: requestId => this.loadPulse(requestId, force),
        calendar: requestId => this.loadCalendar(force, requestId)
      }
      const [pageResults, extraResults] = await Promise.all([this.runSections(loaders, requestId), independentResults, datesPending])
      const results = [...pageResults, ...extraResults]
      if (!this.isCurrentRequest(requestId)) return
      const failed = results.find(result => result.status === 'rejected')
      if (failed) {
        this.errorMessage = this.friendlyError(failed.reason, 'smartInsights.unavailable')
      }
    },
    setSectionLoading (section, active, requestId) {
      if (requestId !== undefined && !this.isCurrentRequest(requestId)) return
      const fields = { dates: 'datesLoading', overview: 'overviewLoading', opinions: 'opinionsLoading', pulse: 'pulseLoading', calendar: 'calendarLoading' }
      if (fields[section]) this[fields[section]] = active
    },
    async loadOverview (requestId, force = false) {
      const cacheKey = this.cacheKey()
      if (!force && this.smartInsightsCache.overview.has(cacheKey)) {
        if (this.isCurrentRequest(requestId)) {
          this.overview = this.smartInsightsCache.overview.get(cacheKey)
          this.watchlist = Array.isArray(this.overview.assets) ? this.overview.assets : []
        }
        return
      }
      const response = await getSmartInsightsOverview({
        as_of: this.asOf,
        lang: (this.$i18n && this.$i18n.locale) || 'en-US'
      })
      if (!this.isCurrentRequest(requestId)) return
      this.smartInsightsCache.overview.set(cacheKey, response.data)
      this.overview = response.data
      this.watchlist = Array.isArray(response.data && response.data.assets) ? response.data.assets : []
    },
    async loadPublicDeepReports (requestId) {
      const assetKeys = ['crypto:BTC/USDT', 'crypto:SOL/USDT', 'crypto:LINK/USDT', 'forex:XAUUSD']
      const responses = await Promise.allSettled(assetKeys.map(assetKey => getPublicResearchReport(assetKey, 'deep')))
      if (!this.isCurrentRequest(requestId) || !this.isGuest) return
      this.publicDeepReports = responses
        .filter(result => result.status === 'fulfilled' && result.value && result.value.code === 1 && result.value.data)
        .map(result => result.value.data)
    },
    async loadSharedResearchReports (requestId) {
      const response = await getSharedResearchReports()
      if (!this.isCurrentRequest(requestId) || this.isGuest) return
      this.sharedResearchStates = response && response.code === 1 && Array.isArray(response.data) ? response.data : []
      this.refreshSelectedSharedResearchRow()
      this.syncSharedReportPolling()
      // Keep the shared/public state visible immediately; private artifacts
      // are heavier and replace it asynchronously when the latest account
      // report has been read.
      this.loadAccountDeepReports(this.sharedResearchStates, requestId).catch(() => {})
    },
    tradingAgentsPayload (response) {
      const value = response && response.data !== undefined ? response.data : response
      return value && value.code === 1 ? value.data : value
    },
    tradingAgentsMarket (asset) {
      const market = String(asset && asset.market || '').trim().toLowerCase()
      if (market === 'gold' || market === 'forex') return 'Gold'
      if (market === 'crypto') return 'Crypto'
      if (market === 'vnstock' || market === 'vn' || market === 'vietnamstock') return 'VNStock'
      if (market === 'usstock' || market === 'us') return 'USStock'
      return String(asset && asset.market || '')
    },
    async loadAccountDeepReports (states, requestId) {
      const assets = new Map()
      for (const state of Array.isArray(states) ? states : []) {
        const asset = state && state.asset
        if (asset) assets.set(opinionAssetKey(asset), asset)
      }
      for (const asset of Array.isArray(this.watchlist) ? this.watchlist : []) {
        assets.set(opinionAssetKey(asset), asset)
      }
      const entries = await Promise.allSettled([...assets.entries()].map(async ([assetKey, asset]) => {
        const payload = this.tradingAgentsPayload(await getTradingAgentsRuns({
          market: this.tradingAgentsMarket(asset),
          symbol: asset.symbol || asset.sym,
          scope: 'history',
          limit: 100
        }))
        const runs = Array.isArray(payload && payload.runs) ? payload.runs : []
        const completed = runs.find(run => ['succeeded', 'completed'].includes(String(run && run.status || '').toLowerCase()))
        if (!completed || !completed.run_id) return null
        const artifactResponse = await getTradingAgentsArtifact(completed.run_id, 'complete_report.md')
        const body = typeof artifactResponse === 'string'
          ? artifactResponse
          : String((artifactResponse && artifactResponse.data) || '')
        if (!body.trim()) return null
        const generatedAt = completed.finished_at || completed.created_at || completed.analysis_date
        return {
          assetKey,
          report: {
            id: `account:${completed.run_id}`,
            source: 'ACCOUNT_PRIVATE_REPORT',
            scope: 'account_private',
            status: 'completed',
            body: body.trim(),
            summary: '',
            decision: null,
            analysisDate: completed.analysis_date || null,
            effectiveDate: completed.analysis_date || null,
            generatedAt,
            createdAt: generatedAt,
            updatedAt: generatedAt,
            inputData: { capturedAt: generatedAt, components: [] },
            accountRunId: completed.run_id
          }
        }
      }))
      if (!this.isCurrentRequest(requestId) || this.isGuest) return
      this.accountDeepReports = entries
        .filter(result => result.status === 'fulfilled' && result.value)
        .map(result => result.value)
      this.refreshSelectedSharedResearchRow()
    },
    async loadDates (requestId, force = false) {
      if (!force && Array.isArray(this.smartInsightsCache.dates)) {
        if (this.isCurrentRequest(requestId)) {
          this.dates = this.smartInsightsCache.dates
          if (!this.asOf && this.dates.length) this.asOf = this.dates[0]
        }
        return
      }
      const response = await getSmartInsightsDates()
      const dates = (response.data && response.data.dates) || []
      if (!this.isCurrentRequest(requestId)) return
      this.smartInsightsCache.dates = dates
      this.dates = dates
      if (!this.asOf && this.dates.length) this.asOf = this.dates[0]
    },
    async loadPulse (requestId, force = false) {
      const cacheKey = this.cacheKey()
      if (!force && this.smartInsightsCache.pulse.has(cacheKey)) {
        if (this.isCurrentRequest(requestId)) {
          this.cryptoPulse = this.smartInsightsCache.pulse.get(cacheKey)
          this.loadPulseDetails(requestId, force).catch(() => {})
        }
        return
      }
      const response = await getSmartInsightsCryptoPulse({ compact: 1, stage: 'summary' })
      if (!this.isCurrentRequest(requestId)) return
      this.smartInsightsCache.pulse.set(cacheKey, response.data)
      this.cryptoPulse = response.data
      this.loadPulseDetails(requestId, force).catch(() => {})
    },
    async loadPulseDetails (requestId, force = false) {
      if (!this.isCurrentRequest(requestId) || this.pulseDetailsLoading) return
      this.pulseDetailsLoading = true
      try {
        await this.loadPulseStage('core', requestId, force)
      } catch (error) {
        if (this.isCurrentRequest(requestId)) this.sectionErrors.pulse = true
      } finally {
        if (this.isCurrentRequest(requestId)) this.pulseDetailsLoading = false
      }
      if (!this.isCurrentRequest(requestId)) return
      this.pulseOnchainLoading = true
      try {
        await this.loadPulseStage('onchain', requestId, force)
      } catch (error) {
        if (this.isCurrentRequest(requestId)) this.sectionErrors.pulse = true
      } finally {
        if (this.isCurrentRequest(requestId)) this.pulseOnchainLoading = false
      }
    },
    async loadPulseStage (stage, requestId, force = false) {
      const cache = stage === 'core' ? this.smartInsightsCache.pulseCore : this.smartInsightsCache.pulseOnchain
      const cacheKey = this.cacheKey()
      if (!force && cache.has(cacheKey)) {
        if (this.isCurrentRequest(requestId)) {
          if (stage === 'core') this.cryptoPulse = cache.get(cacheKey)
          else this.cryptoOnchainPulse = cache.get(cacheKey)
        }
        return
      }
      const response = await getSmartInsightsCryptoPulse({ compact: 1, stage })
      if (!this.isCurrentRequest(requestId)) return
      cache.set(cacheKey, response.data)
      if (stage === 'core') this.cryptoPulse = response.data
      else this.cryptoOnchainPulse = response.data
    },
    async loadCalendar (force = false, requestId) {
      if (this.isCurrentRequest(requestId)) { this.calendarError = ''; this.calendarMeta = {} }
      const lang = (this.$i18n && this.$i18n.locale) || 'en-US'
      const calendarKey = `${this.cacheKey()}|14`
      if (!force && calendarCacheFresh(this.smartInsightsCache.calendar) && this.smartInsightsCache.calendar.key === calendarKey) {
        const cached = this.smartInsightsCache.calendar
        if (this.isCurrentRequest(requestId)) {
          this.calendarEvents = cached.events
          this.calendarMeta = cached.meta
          this.calendarError = cached.error
        }
        return
      }
      try {
        const response = await getEconomicCalendar({ force: force ? 1 : undefined, as_of: this.asOf, days: 14, lang })
        if (!response || response.code !== 1) throw new Error(response && response.msg ? response.msg : this.$t('smartInsights.calendarUnavailable'))
        const events = Array.isArray(response.data) ? response.data : []
        const meta = response.meta || {}
        const error = !events.length && meta.message ? meta.message : ''
        if (!this.isCurrentRequest(requestId)) return
        this.smartInsightsCache.calendar = { key: calendarKey, events, meta, error, loadedAt: Date.now() }
        this.calendarEvents = events
        this.calendarMeta = meta
        this.calendarError = error
      } catch (error) {
        if (!this.isCurrentRequest(requestId)) return
        this.calendarEvents = []
        this.calendarError = this.friendlyError(error, 'smartInsights.calendarLoadFailed')
        throw error
      }
    },
    async retrySection (section) {
      const loaderKey = section
      const loaders = loaderKey === 'opinions'
        ? {
            opinions: requestId => this.loadOverview(requestId, true)
          }
        : {
            overview: requestId => this.loadOverview(requestId, true),
            pulse: requestId => this.loadPulse(requestId, true),
            calendar: requestId => this.loadCalendar(true, requestId)
          }
      if (!loaders[loaderKey]) return
      const requestId = this.requestSequence
      this.errorMessage = ''
      this.retryingSection = section
      try {
        const activeLoaders = {}
        const keys = [loaderKey]
        keys.forEach(key => { activeLoaders[key] = loaders[key] })
        const results = await this.runSections(activeLoaders, requestId)
        if (this.isCurrentRequest(requestId) && results.some(result => result.status === 'rejected')) this.errorMessage = this.friendlyError(results.find(result => result.status === 'rejected').reason, 'smartInsights.unavailable')
      } finally {
        if (this.isCurrentRequest(requestId) && this.retryingSection === section) this.retryingSection = ''
      }
    },
    hasPendingSharedReports () {
      return !this.isGuest && this.sharedResearchStates.some(report => String(report && report.status || '').toLowerCase() === 'pending')
    },
    startSharedReportPolling () {
      if (!this.hasPendingSharedReports()) {
        this.stopSharedReportPolling()
        return
      }
      if (this.sharedReportPollingTimer !== null || typeof window === 'undefined') return
      this.sharedReportPollingTimer = window.setInterval(() => this.refreshPendingSharedReports(), 15000)
    },
    stopSharedReportPolling () {
      if (this.sharedReportPollingTimer !== null && typeof window !== 'undefined') window.clearInterval(this.sharedReportPollingTimer)
      this.sharedReportPollingTimer = null
      this.sharedReportPollingInFlight = false
    },
    syncSharedReportPolling () {
      if (this.hasPendingSharedReports()) this.startSharedReportPolling()
      else this.stopSharedReportPolling()
    },
    async refreshPendingSharedReports () {
      if (this.sharedReportPollingInFlight) return
      if (!this.hasPendingSharedReports()) {
        this.stopSharedReportPolling()
        return
      }
      this.sharedReportPollingInFlight = true
      try {
        await this.loadSharedResearchReports(this.requestSequence)
      } catch (_) {
        // Keep polling while the last known report state is pending; a brief
        // network failure must not turn an in-progress analysis into a stuck UI.
      } finally {
        this.sharedReportPollingInFlight = false
        this.syncSharedReportPolling()
      }
    },
    refreshSelectedSharedResearchRow () {
      if (!this.selectedOpinionRow) return
      const refreshed = this.opinionRows.find(row => row.id === this.selectedOpinionRow.id)
      if (!refreshed) return
      this.selectedOpinionRow = refreshed
      this.publicDeepReport = (refreshed.deepState && refreshed.deepState.report) || null
      if (this.publicDeepReport) this.publicDeepPdfRevision++
    },
    async openAssetAnalysis (row) {
      if (!row) return
      if (this.isGuest && row.researchInDevelopment) return
      this.selectedOpinionRow = row
      this.publicDeepReport = null
      this.publicDeepReportView = 'full'
      this.publicDeepPdfRevision++
      this.publicDeepError = ''
      this.deepAnalysisTarget = {
        market: row && row.market,
        symbol: row && (row.displaySymbol || row.symbol)
      }
      this.analysisMode = 'deep'
      this.deepAnalysisVisible = true
      this.analysisModalVisible = true
      await this.loadPublicDeepReport(row)
    },
    async loadPublicDeepReport (row) {
      if (!row || !row.publicAssetKey) return
      const requestId = ++this.publicDeepRequestId
      this.publicDeepLoading = true
      this.publicDeepReport = null
      this.publicDeepError = ''
      try {
        const response = this.isGuest ? await getPublicResearchReport(row.publicAssetKey, 'deep') : null
        if (requestId !== this.publicDeepRequestId || !this.analysisModalVisible || this.selectedOpinionRow !== row) return
        this.publicDeepReport = this.isGuest ? (response && response.code === 1 ? response.data : null) : ((row.deepState && row.deepState.report) || null)
      } catch (error) {
        if (requestId === this.publicDeepRequestId && this.analysisModalVisible && this.selectedOpinionRow === row) this.publicDeepError = this.$t('smartInsights.aiReportUnavailable')
      } finally {
        if (requestId === this.publicDeepRequestId) this.publicDeepLoading = false
      }
    },
    openBriefHighlight (highlight) {
      const row = this.opinionRows.find(item => item.id === highlight.assetKey)
      if (row) this.openDeepAnalysis(row)
    },
    openAiAssistant (row) {
      if (this.isGuest) {
        const redirect = `/ai-asset-analysis?market=${encodeURIComponent(row.market)}&symbol=${encodeURIComponent(row.displaySymbol)}&action=analyze`
        openAuthModal({ redirect })
        return
      }
      this.$router.push({ path: '/ai-asset-analysis', query: { market: row.market, symbol: row.displaySymbol, action: 'analyze' } })
    },
    openDeepAnalysis (row) {
      this.openAssetAnalysis(row)
    },
    closeDeepAnalysis () {
      this.closeAssetAnalysis()
    },
    closeAssetAnalysis () {
      this.analysisModalVisible = false
      this.deepAnalysisVisible = false
      this.publicDeepRequestId++
      this.publicDeepLoading = false
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
    stopHeroSpeech () {
      if (this.heroSpeechActive && typeof window !== 'undefined' && window.speechSynthesis) window.speechSynthesis.cancel()
      this.heroSpeechActive = false
    },
    closeEvidence () {
      this.evidenceSequence++
      this.evidenceVisible = false
      this.evidenceLoading = false
    },
    async openEvidence (id) {
      const requestId = ++this.evidenceSequence
      this.evidenceVisible = true; this.evidenceLoading = true; this.evidence = null
      try {
        const response = await getSmartInsightsEvidence(id)
        if (requestId === this.evidenceSequence) this.evidence = response.data
      } catch (error) {
        if (requestId === this.evidenceSequence) this.errorMessage = this.friendlyError(error, 'smartInsights.unavailable')
      } finally {
        if (requestId === this.evidenceSequence) this.evidenceLoading = false
      }
    },
    statusLabel (status) {
      const labels = {
        COMPLETE: this.$t('smartInsights.availableStatus'),
        AVAILABLE: this.$t('smartInsights.availableStatus'),
        FRESH: this.$t('smartInsights.availableStatus'),
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
    friendlyError (_cause, key) {
      return this.$t(key)
    },
    pretty (value) { return JSON.stringify(value || {}, null, 2) },
    shortChecksum (value) { const text = String(value || ''); return text ? `${text.slice(0, 10)}...${text.slice(-6)}` : this.$t('smartInsights.notAvailable') },
    formatDate (value) { return formatVietnamDate(value, { locale: this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-GB', fallback: this.$t('smartInsights.dataUnavailableShort') }) },
    formatDateTime (value) {
      if (!value) return this.$t('smartInsights.notAvailable')
      const locale = this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-GB'
      return formatVietnamDateTime(value, { locale, fallback: String(value) })
    },
    marketLabel (value) { const labels = { all: this.$t('smartInsights.all'), crypto: 'Crypto', vn: 'VN', us: 'US', gold: this.$t('smartInsights.gold') }; return labels[value] || String(value || '').toUpperCase() }
  }
}
</script>

<style lang="less" scoped>
.asset-analysis-modal-body { --page-bg: #f7f9fc; --ink: #17253d; --muted: #7b8798; --line: #e4eaf3; --card: #fff; --blue: var(--primary-color, #174ca8); --soft-blue: var(--primary-color-soft, rgba(24,144,255,.1)); max-height: 78vh; padding-right: 4px; overflow-y: auto; color: var(--ink); }
.asset-analysis-modal-body.theme-dark { --page-bg: #111827; --ink: #eef4ff; --muted: #9aa8bc; --line: #2a3547; --card: #182235; --soft-blue: rgba(24,144,255,.16); }
.asset-analysis-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }.asset-analysis-header > div { display: grid; gap: 3px; }.asset-analysis-header strong { color: var(--ink); font-size: 18px; }.asset-analysis-header span { color: var(--muted); font-size: 12px; }
.asset-analysis-meta { display: flex; flex-wrap: wrap; gap: 12px; padding: 10px 0; color: var(--muted); font-size: 12px; }
.public-deep-report { display: grid; gap: 10px; }
.public-deep-report > small { color: var(--muted); font-size: 11px; }
.analysis-mode-switcher { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 14px 0 2px; padding: 4px; border: 1px solid var(--line); border-radius: 12px; background: var(--page-bg); }.analysis-mode-option { display: flex; align-items: center; gap: 9px; min-width: 0; padding: 10px 12px; border: 1px solid transparent; border-radius: 9px; color: var(--muted); text-align: left; background: transparent; cursor: pointer; transition: border-color .18s ease, background .18s ease, color .18s ease, transform .18s ease; }.analysis-mode-option:hover, .analysis-mode-option:focus-visible { color: var(--ink); background: var(--card); outline: 0; }.analysis-mode-option:active { transform: translateY(1px) scale(.99); }.analysis-mode-option.active { border-color: var(--blue-ring); color: var(--blue); background: var(--card); box-shadow: 0 3px 10px var(--blue-ring); }.analysis-mode-option > .anticon { flex: 0 0 auto; font-size: 16px; }.analysis-mode-option span { display: grid; min-width: 0; gap: 2px; }.analysis-mode-option strong { color: inherit; font-size: 13px; }.analysis-mode-option small { overflow: hidden; color: var(--muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.analysis-deep-intro { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-top: 14px; padding: 12px 13px; border: 1px solid var(--line); border-radius: 10px; background: var(--soft-blue); }.analysis-deep-intro > div { display: grid; gap: 3px; min-width: 0; }.analysis-deep-intro strong { color: var(--ink); font-size: 14px; }.analysis-deep-intro span { color: var(--muted); font-size: 12px; line-height: 1.45; }.analysis-deep-intro .ant-tag { flex: 0 0 auto; margin: 0; }
.public-report-view-switcher { display: grid; gap: 7px; margin-top: 12px; }.public-report-view-switcher > span { color: var(--muted); font-size: 12px; line-height: 1.45; }
.analysis-drawer-section { margin-top: 16px; padding: 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--card); }.analysis-drawer-section-title { display: flex; align-items: center; gap: 7px; }.analysis-drawer-section-title .anticon { color: var(--blue); }.analysis-drawer-section-title h3 { margin: 0; color: var(--ink); font-size: 15px; }.analysis-result-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }.analysis-result-grid > div { display: grid; gap: 4px; padding: 9px 10px; border-radius: 8px; background: var(--soft-blue); }.analysis-result-grid small { color: var(--muted); font-size: 11px; }.analysis-result-grid strong { color: var(--ink); font-size: 16px; }.analysis-copy { margin-top: 13px; }.analysis-copy h4 { margin: 0 0 5px; color: var(--ink); font-size: 13px; }.analysis-copy p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.65; white-space: pre-wrap; }.analysis-report { margin-top: 13px; overflow: auto; color: var(--ink); font-size: 13px; line-height: 1.6; }.analysis-report :deep(.qd-report) { max-width: 100%; }
.analysis-evidence-desc { margin: 5px 0 10px; color: var(--muted); font-size: 12px; }.analysis-evidence-list { display: grid; gap: 8px; }.analysis-evidence-item { padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--page-bg); }.analysis-evidence-item-head, .analysis-evidence-item-meta { display: flex; justify-content: space-between; gap: 10px; }.analysis-evidence-item-head strong { color: var(--ink); font-size: 13px; }.analysis-evidence-item-head span, .analysis-evidence-item-meta { color: var(--muted); font-size: 11px; }.analysis-evidence-item-meta { margin-top: 4px; flex-wrap: wrap; }.analysis-evidence-item-copy { margin: 8px 0 0; color: var(--ink); font-size: 13px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }.analysis-evidence-item a { display: block; overflow: hidden; margin-top: 7px; color: var(--blue); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.analysis-evidence-item pre { max-height: 150px; margin: 8px 0 0; padding: 8px; overflow: auto; border-radius: 6px; color: var(--ink); background: var(--card); font-size: 11px; white-space: pre-wrap; word-break: break-word; }.analysis-empty { display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 7px; min-height: 90px; color: var(--muted); text-align: center; }.analysis-empty p { margin: 0; font-size: 13px; }.analysis-empty a { color: var(--blue); font-size: 13px; }.analysis-empty--compact { min-height: 48px; }
.legacy-page { --page-bg: #f7f9fc; --ink: #17253d; --muted: #7b8798; --line: #e4eaf3; --card: #fff; --blue: var(--primary-color, #174ca8); --blue-hover: var(--primary-color-hover, #40a9ff); --blue-active: var(--primary-color-active, #096dd9); --blue-ring: var(--primary-color-ring, rgba(24,144,255,.22)); --soft-blue: var(--primary-color-soft, rgba(24,144,255,.1)); --soft-blue-strong: var(--primary-color-soft-strong, rgba(24,144,255,.18)); position: relative; min-height: calc(100vh - 64px); overflow: hidden; color: var(--ink); background: var(--page-bg); font-size: 15px; }
.legacy-main, .footer-inner, .footer-bottom { width: 100%; max-width: 1120px; margin: 0 auto; }
.legacy-main { width: 100%; max-width: 1480px; margin: 0 auto; box-sizing: border-box; padding: 24px 28px 48px; }.analysis-controls { display: flex; align-items: end; gap: 10px; min-height: 40px; margin-bottom: 17px; }.date-control { display: grid; grid-template-columns: auto 130px; align-items: center; gap: 8px; }.date-control label { color: var(--muted); font-size: 13px; font-weight: 600; }.date-control .ant-select { width: 130px; }.analysis-controls .ant-btn, .analysis-controls .ant-radio-button-wrapper, .date-control .ant-select-selection-selected-value { font-size: 13px; }.control-spacer { flex: 1; }.legacy-alert { margin-bottom: 12px; }.initial-overview-loading { min-height: 184px; padding: 34px 38px; border: 1px solid var(--line); border-radius: 17px; background: var(--card); box-shadow: 0 8px 24px var(--blue-ring); }
.daily-hero { display: flex; align-items: center; justify-content: space-between; min-height: 184px; padding: 30px 38px; overflow: hidden; border-radius: 17px; color: #fff; background: linear-gradient(115deg, var(--blue-active) 0%, var(--blue) 52%, var(--blue-hover) 122%); box-shadow: 0 14px 28px var(--blue-ring); }.hero-copy { position: relative; z-index: 1; min-width: 0; }.hero-kicker { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; color: rgba(255,255,255,.78); font-size: 12px; }.hero-badge, .hero-status { padding: 4px 9px; border: 1px solid rgba(255,255,255,.2); border-radius: 999px; background: rgba(255,255,255,.12); }.hero-badge { font-weight: 700; }.daily-hero h1 { max-width: 620px; margin: 0 0 9px; color: #fff; font-size: clamp(30px, 4vw, 42px); line-height: 1.08; letter-spacing: -.04em; }.daily-hero p { margin: 0; color: rgba(255,255,255,.82); font-size: 13px; }.hero-thesis { margin-top: 6px !important; color: rgba(255,255,255,.62) !important; }.hero-arrow { color: var(--blue-hover); }.daily-brief-highlights { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; max-width: 860px; margin-top: 14px; }.brief-highlight { display: grid; gap: 6px; min-width: 0; padding: 10px 11px; border: 1px solid rgba(255,255,255,.18); border-radius: 10px; color: #fff; text-align: left; background: rgba(255,255,255,.1); cursor: pointer; transition: background .18s ease, border-color .18s ease, transform .18s ease; }.brief-highlight:hover, .brief-highlight:focus-visible { border-color: rgba(255,255,255,.42); background: rgba(255,255,255,.18); outline: 0; transform: translateY(-1px); }.brief-highlight-head { display: flex; align-items: center; gap: 7px; min-width: 0; }.brief-highlight-head strong { font-size: 13px; }.brief-highlight-decision { font-size: 11px; font-weight: 700; }.brief-highlight-decision.analysis-positive { color: #b9f5d8 !important; }.brief-highlight-decision.analysis-negative { color: #ffd1d1 !important; }.brief-highlight-decision.analysis-neutral { color: rgba(255,255,255,.76) !important; }.brief-highlight-confidence { margin-left: auto; color: rgba(255,255,255,.68); font-size: 10px; }.brief-highlight-summary { display: -webkit-box; overflow: hidden; color: rgba(255,255,255,.78); font-size: 11px; line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }.brief-highlight-link { color: rgba(255,255,255,.9); font-size: 10px; font-weight: 700; }.hero-audio { display: flex; align-items: center; gap: 12px; min-width: 190px; padding: 11px 15px; border: 1px solid rgba(255,255,255,.18); border-radius: 12px; color: #fff; text-align: left; background: rgba(255,255,255,.1); opacity: .7; }.hero-audio strong, .hero-audio small { display: block; }.hero-audio strong { font-size: 13px; }.hero-audio small { margin-top: 3px; color: rgba(255,255,255,.62); font-size: 11px; }.play-button { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%; color: var(--blue); background: rgba(255,255,255,.75); }
.legacy-card { margin-top: 16px; overflow: hidden; border: 1px solid var(--line); border-radius: 12px; background: var(--card); box-shadow: 0 3px 12px var(--blue-ring); }.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 17px; border-bottom: 1px solid var(--line); background: linear-gradient(var(--soft-blue), var(--card)); }.heading-with-icon { display: flex; align-items: flex-start; gap: 9px; min-width: 0; }.section-icon { display: inline-grid; place-items: center; flex: 0 0 auto; width: 30px; height: 30px; border-radius: 8px; color: #fff; background: var(--blue); font-size: 17px; font-weight: 700; }.card-heading h2 { margin: 0; color: var(--ink); font-size: 16px; line-height: 1.3; }.card-heading p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }.card-heading h2 .ant-tag { vertical-align: 2px; color: #18a575; border-color: #b7ead6; background: #ecfbf4; }
.change-list { width: 100%; }.change-row { display: grid; grid-template-columns: 1.1fr 1fr 20px; align-items: center; gap: 12px; min-height: 52px; padding: 10px 16px; border-bottom: 1px solid var(--line); }.change-row:last-child { border-bottom: 0; }.change-row > div:first-child { display: grid; gap: 2px; }.change-row strong { font-size: 13px; }.change-row span, .change-row small { color: var(--muted); font-size: 12px; }.change-detail { display: flex; justify-content: space-between; gap: 10px; }.legacy-empty { display: flex; align-items: center; justify-content: center; gap: 9px; color: var(--muted); text-align: center; }.legacy-empty div { display: grid; gap: 4px; text-align: left; }.legacy-empty span, .legacy-empty strong { font-size: 13px; }.calendar-empty { min-height: 120px; flex-direction: column; }
.brief-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; padding: 1px; background: var(--line); }.brief-facts > div { display: grid; gap: 5px; min-height: 72px; padding: 14px 16px; background: var(--card); }.brief-facts small { color: var(--muted); font-size: 11px; }.brief-facts strong, .brief-facts code { color: var(--ink); font-size: 14px; font-variant-numeric: tabular-nums; }.brief-facts code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.risk-alerts { display: grid; gap: 8px; margin-top: 12px; }.risk-alerts .ant-alert { border-radius: 9px; }.crypto-calendar { margin-top: 18px; }.calendar-filters { display: flex; gap: 4px; }.calendar-filters .ant-btn { padding: 0 9px; font-size: 12px; }
.legacy-footer { margin-top: 22px; border-top: 1px solid var(--line); background: var(--card); }.footer-inner { display: grid; grid-template-columns: 1.5fr 1fr; gap: 24px; padding: 36px 0 30px; }.legacy-brand { display: inline-flex; align-items: center; gap: 6px; color: var(--ink); white-space: nowrap; }.brand-mark { display: inline-grid; place-items: center; width: 25px; height: 25px; border-radius: 6px; color: #fff; background: var(--blue); font-size: 14px; font-weight: 800; }.footer-inner p { max-width: 320px; margin: 10px 0 0; color: var(--muted); font-size: 12px; line-height: 1.7; }.footer-inner > div:last-child { display: grid; align-content: start; gap: 6px; justify-self: end; min-width: 150px; }.footer-inner h3 { margin: 0 0 3px; color: var(--muted); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }.footer-inner a { color: var(--muted); font-size: 12px; text-decoration: none; }.footer-bottom { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-top: 1px solid var(--line); color: var(--muted); font-size: 11px; }.footer-bottom span:first-child { max-width: 720px; }.demo-watermark { position: fixed; right: 4vw; bottom: 8vh; z-index: 0; color: rgba(190,110,10,.08); font-size: 15vw; font-weight: 800; transform: rotate(-12deg); pointer-events: none; }
.theme-dark { --page-bg: #0c1118; --ink: #e9eff7; --muted: #9ba9ba; --line: #263341; --card: #121a23; --soft-blue: var(--primary-color-soft-strong, rgba(24,144,255,.18)); --soft-blue-strong: var(--primary-color-soft-strong, rgba(24,144,255,.18)); }.theme-dark .legacy-footer { background: var(--card); }.theme-dark .card-heading { background: linear-gradient(var(--soft-blue), var(--card)); }.theme-dark .change-row { border-color: var(--line); }.theme-dark .footer-inner a { color: var(--muted); }
.analysis-metric-grid, .analysis-factor-grid, .analysis-consensus-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }.analysis-metric-item, .analysis-factor-item, .analysis-consensus-grid > div { display: grid; gap: 4px; min-width: 0; padding: 9px 10px; border-radius: 8px; background: var(--soft-blue); }.analysis-metric-item small, .analysis-factor-item small, .analysis-consensus-grid small { color: var(--muted); font-size: 11px; }.analysis-metric-item strong, .analysis-factor-item strong, .analysis-consensus-grid strong { overflow-wrap: anywhere; color: var(--ink); font-size: 13px; }.analysis-positive { color: #1b9a6c !important; }.analysis-negative { color: #d55353 !important; }.analysis-neutral { color: var(--muted) !important; }.analysis-detail-list { display: grid; gap: 9px; margin-top: 12px; }.analysis-detail-item { padding: 11px 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--page-bg); }.analysis-detail-item-title { display: flex; align-items: center; gap: 7px; color: var(--ink); font-size: 13px; }.analysis-detail-item-title .anticon { color: var(--blue); }.analysis-detail-item p { margin: 7px 0 0; color: var(--ink); font-size: 13px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }.analysis-bullet-list { display: grid; gap: 7px; margin: 12px 0 0; padding-left: 18px; color: var(--ink); font-size: 12px; line-height: 1.55; }.analysis-bullet-list li { overflow-wrap: anywhere; }.analysis-bullet-list li strong { margin-right: 6px; }.analysis-trend-list { display: grid; gap: 6px; margin-top: 12px; }.analysis-trend-item { display: grid; grid-template-columns: minmax(90px, 1fr) auto auto; align-items: center; gap: 8px; padding: 8px 10px; border-bottom: 1px solid var(--line); color: var(--muted); font-size: 12px; }.analysis-trend-item:last-child { border-bottom: 0; }.analysis-trend-item strong { font-size: 12px; }.analysis-trend-item small { color: var(--muted); }.analysis-risks { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--line); }.analysis-risks h4 { margin: 0; color: var(--ink); font-size: 13px; }
@media (max-width: 960px) { .legacy-main { width: 100%; }.analysis-controls { flex-wrap: wrap; align-items: stretch; }.control-spacer { display: none; }.date-control { flex: 1 1 100%; grid-template-columns: auto 118px; } }
@media (max-width: 900px) and (min-width: 681px) { .analysis-metric-grid, .analysis-factor-grid, .analysis-consensus-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .legacy-main { padding: 14px 12px 32px; }.date-control { grid-template-columns: auto 1fr; }.date-control .ant-select { width: 100%; }.daily-hero { align-items: flex-start; flex-direction: column; gap: 22px; padding: 25px 22px; }.daily-hero h1 { font-size: 32px; }.daily-brief-highlights { grid-template-columns: 1fr; width: 100%; }.hero-audio { width: 100%; }.card-heading { align-items: flex-start; flex-direction: column; }.calendar-filters { flex-wrap: wrap; }.brief-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }.analysis-mode-switcher { grid-template-columns: 1fr; gap: 4px; }.analysis-mode-option { min-height: 48px; }.analysis-deep-intro { align-items: stretch; flex-direction: column; }.analysis-result-grid, .analysis-metric-grid, .analysis-factor-grid, .analysis-consensus-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.analysis-trend-item { grid-template-columns: 1fr auto; }.analysis-trend-item small { grid-column: 1 / -1; }.asset-analysis-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }.footer-inner { width: calc(100% - 24px); grid-template-columns: 1fr; }.footer-inner > div:last-child { justify-self: start; }.footer-bottom { width: calc(100% - 24px); flex-direction: column; } }
.theme-dark ::v-deep .flow-terminal,
.theme-dark ::v-deep .derivatives-terminal,
.theme-dark ::v-deep .cycle-terminal,
.theme-dark ::v-deep .onchain-terminal { background: var(--page-bg); }
.theme-dark ::v-deep .metric-card,
.theme-dark ::v-deep .metric-card.unavailable,
.theme-dark ::v-deep .halving-context { background: var(--card); border-color: var(--line); }
.theme-dark ::v-deep .metric-copy small { color: var(--ink); }
.theme-dark ::v-deep .flow-table-card th,
.theme-dark ::v-deep .asset-rail button.active { background: var(--soft-blue); }
</style>

<style lang="less">
.asset-analysis-modal .ant-modal { max-width: calc(100vw - 24px); }
.asset-analysis-modal .ant-modal-content { overflow: hidden; border-radius: 14px; box-shadow: 0 20px 60px rgba(12, 28, 52, .22); }
.asset-analysis-modal .ant-modal-header { padding: 16px 20px; border-bottom-color: #e4eaf3; }
.asset-analysis-modal .ant-modal-body { max-height: calc(100vh - 140px); padding: 16px 18px 18px; }
.asset-analysis-modal--hub .trading-agents-modal--embedded.ant-modal-wrap { position: static !important; z-index: auto; height: auto; overflow: visible; }
.asset-analysis-modal--hub .trading-agents-modal--embedded .ant-modal { top: 0; width: 100% !important; max-width: none; padding-bottom: 0; }
.asset-analysis-modal--hub .trading-agents-modal--embedded .ant-modal-content { border: 0; border-radius: 0; box-shadow: none; background: transparent; }
.asset-analysis-modal--hub .trading-agents-modal--embedded .ant-modal-body { padding: 0; }
.asset-analysis-modal--hub .trading-agents-modal--embedded .deep-analysis-panel { padding-top: 10px; }
.asset-analysis-modal.theme-dark .ant-modal-content, .asset-analysis-modal.theme-dark .ant-modal-header { color: #eef4ff; border-color: #2a3547; background: #182235; }
.asset-analysis-modal.theme-dark .ant-modal-title, .asset-analysis-modal.theme-dark .ant-modal-close { color: #eef4ff; }
@media (max-width: 680px) { .asset-analysis-modal .ant-modal { width: calc(100vw - 16px) !important; max-width: calc(100vw - 16px); margin: 8px auto; }.asset-analysis-modal .ant-modal-header { padding: 14px 16px; }.asset-analysis-modal .ant-modal-body { max-height: calc(100vh - 72px); padding: 12px 10px 14px; }.asset-analysis-modal-body { max-height: calc(100vh - 112px); padding-right: 0; }.asset-analysis-modal--hub .trading-agents-modal--embedded .ant-modal { margin: 0; }.analysis-drawer-section { margin-top: 10px; padding: 11px; }.analysis-drawer-section-title h3 { font-size: 14px; }.analysis-copy p, .analysis-detail-item p, .analysis-evidence-item-copy { font-size: 12px; line-height: 1.55; }.analysis-metric-item, .analysis-factor-item, .analysis-consensus-grid > div { padding: 8px; }.analysis-metric-item strong, .analysis-factor-item strong, .analysis-consensus-grid strong { font-size: 12px; } }
</style>
