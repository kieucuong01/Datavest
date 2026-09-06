<template>
  <a-modal
    :visible="visible"
    :title="title"
    :width="960"
    :footer="null"
    centered
    :mask-closable="!isRunning"
    :keyboard="!isRunning"
    :wrap-class-name="'trading-agents-modal'"
    @cancel="close"
  >
    <section class="deep-analysis-panel" :class="{ 'theme-dark': dark }" aria-live="polite">
      <div class="deep-analysis-context">
        <div>
          <span class="deep-analysis-kicker"><a-icon type="apartment" /> {{ $t('tradingAgents.nativeGraph') }}</span>
          <h3>{{ targetLabel }}</h3>
          <p>{{ $t('tradingAgents.fullGraphDescription') }}</p>
        </div>
        <div class="deep-analysis-provenance">
          <a-tag color="blue">{{ marketLabel }}</a-tag>
          <a-tag>{{ analysisDate || vietnamToday }}</a-tag>
          <a-tag v-if="run && run.source_pin">{{ $t('tradingAgents.sourcePinned') }}</a-tag>
        </div>
      </div>

      <a-alert
        v-if="!isSupported"
        type="warning"
        show-icon
        :message="$t('tradingAgents.unsupportedTitle')"
        :description="$t('tradingAgents.unsupportedDescription')"
      />
      <a-alert
        v-else-if="errorMessage"
        type="error"
        show-icon
        :message="$t('tradingAgents.errorTitle')"
        :description="errorMessage"
        class="deep-analysis-error"
      />

      <div v-if="historyLoading && !run && isSupported" class="deep-analysis-history-loading">
        <a-spin size="small" /> {{ $t('tradingAgents.loadingExisting') }}
      </div>

      <div v-else-if="!run && isSupported && historyError" class="deep-analysis-empty deep-analysis-empty--error">
        <a-icon type="warning" />
        <h4>{{ $t('tradingAgents.errorTitle') }}</h4>
        <p>{{ historyError }}</p>
        <div class="history-recovery-actions">
          <a-button type="primary" :loading="historyLoading" @click="loadLatestRun({ autoStart: true })">
            <a-icon type="reload" /> {{ $t('tradingAgents.historyRetry') }}
          </a-button>
          <a-button :loading="starting" @click="start">
            <a-icon type="thunderbolt" /> {{ $t('tradingAgents.startAfterHistoryError') }}
          </a-button>
        </div>
      </div>

      <div v-else-if="!run && isSupported" class="deep-analysis-empty">
        <a-icon type="radar-chart" />
        <h4>{{ $t('tradingAgents.readyTitle') }}</h4>
        <p>{{ $t('tradingAgents.readyDescription') }}</p>
        <a-button type="primary" size="large" :loading="starting" @click="start">
          <a-icon type="thunderbolt" /> {{ $t('tradingAgents.start') }}
        </a-button>
      </div>

      <template v-else-if="run">
        <div class="deep-analysis-status-row">
          <span class="run-state" :class="`run-state--${String(run.status || 'queued').toLowerCase()}`">
            <a-icon :type="statusIcon" /> {{ statusLabel }}
          </span>
          <span v-if="run.created_at" class="run-time">{{ $t('tradingAgents.createdAt') }}: {{ formatDateTime(run.created_at) }}</span>
        </div>

        <div v-if="isRunning" class="deep-analysis-progress">
          <div class="progress-topline">
            <div class="progress-title">
              <span class="progress-live-dot" aria-hidden="true" />
              <strong>{{ $t('tradingAgents.runningTitle') }}</strong>
              <span>{{ $t('tradingAgents.completedStages', { completed: progressSnapshot.completed_count || 0, total: progressTotal }) }}</span>
            </div>
            <strong class="progress-percent">{{ progressPercent }}%</strong>
          </div>
          <a-progress :percent="progressPercent" :show-info="false" :stroke-width="8" status="active" />
          <div class="progress-current-card">
            <span class="progress-current-icon"><a-icon type="loading" /></span>
            <div class="progress-current-copy">
              <span class="progress-current-label">{{ $t('tradingAgents.currentStage') }}</span>
              <strong>{{ currentStageLabel }}</strong>
              <p>{{ currentStageDescription }}</p>
            </div>
            <div class="progress-time">
              <strong>{{ progressElapsedLabel }}</strong>
              <span>{{ progressTotalElapsedLabel }}</span>
            </div>
          </div>
          <div class="progress-footnote">
            <a-icon type="sync" /> {{ progressHeartbeatLabel }}
          </div>
          <div class="progress-actions">
            <a-button size="small" :loading="cancelling" @click="cancel">
              <a-icon type="stop" /> {{ $t('tradingAgents.cancel') }}
            </a-button>
          </div>
          <div class="deep-analysis-stage-list" role="list" :aria-label="$t('tradingAgents.currentStage')">
            <div v-for="(stage, index) in progressStages" :key="stage.id" class="deep-analysis-stage" :class="{ 'is-complete': stage.complete, 'is-current': stage.current, 'is-pending': !stage.complete && !stage.current }" role="listitem">
              <span class="deep-analysis-stage-marker"><a-icon :type="stage.complete ? 'check' : (stage.current ? 'loading' : 'clock-circle')" /></span>
              <span class="deep-analysis-stage-copy">
                <small>{{ String(index + 1).padStart(2, '0') }}</small>
                <span>{{ stage.label }}</span>
              </span>
            </div>
          </div>
        </div>

        <div v-else-if="isResumable" class="deep-analysis-recovery">
          <a-alert type="warning" show-icon :message="$t('tradingAgents.interruptedTitle')" :description="run.failure_message || $t('tradingAgents.interruptedDescription')" />
          <div class="recovery-actions">
            <a-button type="primary" :loading="resuming" @click="resume"><a-icon type="reload" /> {{ $t('tradingAgents.resume') }}</a-button>
            <a-button :loading="clearing" @click="clearCheckpoint"><a-icon type="clear" /> {{ $t('tradingAgents.clearCheckpoint') }}</a-button>
            <a-button @click="startFresh"><a-icon type="plus" /> {{ $t('tradingAgents.startFresh') }}</a-button>
          </div>
        </div>

        <section v-if="reportContent" class="deep-analysis-report" aria-labelledby="deep-analysis-report-title">
          <div class="report-heading">
            <div class="report-heading-copy">
              <span class="report-eyebrow"><a-icon type="file-text" /> {{ $t('tradingAgents.reportTitle') }}</span>
              <h4 id="deep-analysis-report-title">{{ targetLabel }}</h4>
              <span>{{ $t('tradingAgents.reportProvenance') }}</span>
            </div>
            <div class="report-heading-tags">
              <a-tag color="blue"><a-icon type="global" /> {{ reportLanguageLabel }}</a-tag>
              <a-tag color="green"><a-icon type="safety-certificate" /> {{ $t('tradingAgents.researchOnly') }}</a-tag>
            </div>
          </div>
          <div class="report-meta-grid">
            <div><span>{{ $t('tradingAgents.reportDate') }}</span><strong>{{ reportDate }}</strong></div>
            <div><span>{{ $t('tradingAgents.reportSource') }}</span><strong>{{ $t('tradingAgents.nativeGraph') }}</strong></div>
            <div><span>{{ $t('tradingAgents.reportRunId') }}</span><strong>{{ run.run_id }}</strong></div>
          </div>
          <div class="report-body">
            <div v-if="reportSections.length" class="report-sections">
              <article v-for="(section, sectionIndex) in reportSections" :key="`${section.title}-${sectionIndex}`" class="report-section" :class="{ 'is-open': isReportSectionOpen(sectionIndex) }">
                <button
                  type="button"
                  class="report-section-heading"
                  :aria-expanded="isReportSectionOpen(sectionIndex)"
                  :aria-controls="`report-section-content-${sectionIndex}`"
                  :aria-label="$t('tradingAgents.toggleReportSection', { section: localizeHeading(section.title) })"
                  @click="toggleReportSection(sectionIndex)"
                >
                  <span class="report-section-number">{{ String(sectionIndex + 1).padStart(2, '0') }}</span>
                  <span class="report-section-icon"><a-icon :type="reportSectionIcon(section.title)" /></span>
                  <span class="report-section-heading-copy">
                    <h5>{{ localizeHeading(section.title) }}</h5>
                  </span>
                  <a-icon class="report-section-chevron" :type="isReportSectionOpen(sectionIndex) ? 'up' : 'down'" aria-hidden="true" />
                </button>
                <div
                  :id="`report-section-content-${sectionIndex}`"
                  v-show="isReportSectionOpen(sectionIndex)"
                  class="report-section-content"
                  :aria-hidden="!isReportSectionOpen(sectionIndex)"
                >
                  <div v-for="(block, blockIndex) in section.blocks" :key="`${sectionIndex}-${block.type}-${blockIndex}`" class="report-block" :class="`report-block--${block.type}`">
                    <h6 v-if="block.type === 'heading'">{{ localizeHeading(block.text) }}</h6>
                    <ul v-else-if="block.type === 'list'" class="report-list">
                      <li v-for="(item, itemIndex) in block.items" :key="`${sectionIndex}-${blockIndex}-${itemIndex}`">{{ item }}</li>
                    </ul>
                    <div v-else-if="block.type === 'table'" class="report-table-wrap">
                      <table class="report-table">
                        <thead><tr><th v-for="(header, headerIndex) in block.headers" :key="`${sectionIndex}-${blockIndex}-header-${headerIndex}`">{{ header }}</th></tr></thead>
                        <tbody><tr v-for="(row, rowIndex) in block.rows" :key="`${sectionIndex}-${blockIndex}-row-${rowIndex}`"><td v-for="(cell, cellIndex) in row" :key="`${sectionIndex}-${blockIndex}-${rowIndex}-${cellIndex}`">{{ cell }}</td></tr></tbody>
                      </table>
                    </div>
                    <p v-else>{{ block.text }}</p>
                  </div>
                </div>
              </article>
            </div>
            <div v-else class="report-empty">{{ $t('tradingAgents.reportEmpty') }}</div>
          </div>
        </section>
        <div v-else-if="run.status === 'succeeded'" class="deep-analysis-report-loading">
          <a-spin size="small" /> {{ $t('tradingAgents.loadingReport') }}
        </div>
      </template>

      <div class="deep-analysis-footer">
        <span><a-icon type="info-circle" /> {{ $t('tradingAgents.disclaimer') }}</span>
        <a-button :disabled="isRunning" @click="close">{{ $t('tradingAgents.close') }}</a-button>
      </div>
    </section>
  </a-modal>
</template>

<script>
import {
  cancelTradingAgentsRun,
  clearTradingAgentsCheckpoint,
  createTradingAgentsRun,
  getTradingAgentsArtifact,
  getTradingAgentsRun,
  getTradingAgentsRuns,
  resumeTradingAgentsRun
} from '@/api/trading-agents'
import {
  groupTradingAgentsReportSections,
  localizeTradingAgentsHeading,
  parseTradingAgentsReport
} from '@/utils/tradingAgentsReport'
import { formatVietnamDateTime } from '@/utils/vietnamTime'

const FULL_ANALYSTS = ['market', 'social', 'news', 'fundamentals']
const TERMINAL = new Set(['succeeded', 'failed', 'cancelled'])
const HISTORY_TIMEOUT_MS = 8000
const PROGRESS_STAGE_IDS = ['market', 'social', 'news', 'fundamentals', 'investment_debate', 'research_manager', 'trader', 'risk_debate', 'portfolio_manager', 'report']

function vietnamDay () {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).formatToParts(new Date())
  const part = type => parts.find(item => item.type === type).value
  return `${part('year')}-${part('month')}-${part('day')}`
}

export default {
  name: 'DeepAnalysisPanel',
  props: {
    visible: { type: Boolean, default: false },
    target: { type: Object, default: null },
    analysisDate: { type: String, default: '' },
    dark: { type: Boolean, default: false }
  },
  data () {
    return {
      run: null,
      reportContent: '',
      starting: false,
      cancelling: false,
      resuming: false,
      clearing: false,
      errorMessage: '',
      pollTimer: null,
      progressTimer: null,
      progressClock: Date.now(),
      historyLoading: false,
      historyRequestId: 0,
      historyError: '',
      openReportSections: {}
    }
  },
  computed: {
    vietnamToday () { return vietnamDay() },
    isVietnamese () { return this.$i18n && this.$i18n.locale === 'vi-VN' },
    normalizedTarget () {
      const raw = this.target || {}
      const market = String(raw.market || '').toLowerCase()
      const symbol = String(raw.symbol || raw.displaySymbol || '').trim().toUpperCase()
      if (market === 'crypto') return { market: 'Crypto', symbol: symbol.includes('/') || symbol.endsWith('-USD') ? symbol : `${symbol}/USDT` }
      if (['vn', 'vnstock', 'vietnamstock', 'vietnam-stock'].includes(market)) return { market: 'VNStock', symbol }
      if (['gold', 'xau', 'forex'].includes(market) && ['XAU', 'XAUUSD'].includes(symbol)) return { market: 'Gold', symbol }
      return { market: '', symbol }
    },
    isSupported () { return Boolean(this.normalizedTarget.market && this.normalizedTarget.symbol) },
    targetLabel () { return this.normalizedTarget.symbol || this.$t('tradingAgents.noSymbol') },
    marketLabel () { return this.normalizedTarget.market || this.$t('tradingAgents.unavailable') },
    isRunning () { return this.run && ['queued', 'running'].includes(String(this.run.status || '').toLowerCase()) },
    isResumable () { return this.run && ['failed', 'cancelled'].includes(String(this.run.status || '').toLowerCase()) },
    statusLabel () {
      const status = String((this.run && this.run.status) || 'queued').toLowerCase()
      return this.$t(`tradingAgents.status.${status}`)
    },
    statusIcon () {
      const status = String((this.run && this.run.status) || 'queued').toLowerCase()
      return ({ queued: 'clock-circle', running: 'loading', succeeded: 'check-circle', failed: 'warning', cancelled: 'stop' })[status] || 'clock-circle'
    },
    progressStageIds () {
      return this.normalizedTarget.market === 'Crypto'
        ? PROGRESS_STAGE_IDS.filter(id => id !== 'fundamentals')
        : PROGRESS_STAGE_IDS
    },
    progressSnapshot () {
      const progress = this.run && this.run.progress
      if (progress && typeof progress === 'object') return progress
      return {
        percent: this.run ? (String(this.run.status || '').toLowerCase() === 'succeeded' ? 100 : 0) : 0,
        current_stage_id: 'initializing',
        stage_ids: this.progressStageIds,
        completed_stage_ids: [],
        completed_count: 0,
        total_count: this.progressStageIds.length,
        elapsed_seconds: 0,
        total_elapsed_seconds: 0,
        stage_started_at: null,
        heartbeat_count: 0
      }
    },
    progressPercent () {
      const percent = Number(this.progressSnapshot.percent)
      return Number.isFinite(percent) ? Math.min(100, Math.max(0, Math.round(percent))) : 0
    },
    currentStageLabel () {
      const stageId = this.progressSnapshot.current_stage_id || 'initializing'
      return this.$t(`tradingAgents.stages.${stageId}`)
    },
    currentStageDescription () {
      const stageId = this.progressSnapshot.current_stage_id || 'initializing'
      return this.$t(`tradingAgents.stageDetails.${stageId}`)
    },
    progressTotal () {
      return Number(this.progressSnapshot.total_count) || PROGRESS_STAGE_IDS.length
    },
    progressStages () {
      const completed = new Set(this.progressSnapshot.completed_stage_ids || [])
      const current = this.progressSnapshot.current_stage_id
      const stageIds = Array.isArray(this.progressSnapshot.stage_ids) && this.progressSnapshot.stage_ids.length
        ? this.progressSnapshot.stage_ids
        : PROGRESS_STAGE_IDS
      return stageIds.map(id => ({
        id,
        label: this.$t(`tradingAgents.stages.${id}`),
        complete: completed.has(id),
        current: current === id
      }))
    },
    reportBlocks () {
      return parseTradingAgentsReport(this.reportContent)
    },
    reportSections () {
      return groupTradingAgentsReportSections(this.reportBlocks).sections
    },
    progressElapsedSeconds () {
      const reported = Number(this.progressSnapshot.elapsed_seconds) || 0
      const startedAt = Date.parse(this.progressSnapshot.stage_started_at || '')
      if (!this.isRunning || !Number.isFinite(startedAt)) return reported
      return Math.max(reported, Math.floor((this.progressClock - startedAt) / 1000))
    },
    progressTotalElapsedSeconds () {
      const reported = Number(this.progressSnapshot.total_elapsed_seconds) || 0
      const startedAt = Date.parse((this.run && this.run.started_at) || '')
      if (!this.isRunning || !Number.isFinite(startedAt)) return reported
      return Math.max(reported, Math.floor((this.progressClock - startedAt) / 1000))
    },
    progressElapsedLabel () {
      return this.formatDuration(this.progressElapsedSeconds)
    },
    progressTotalElapsedLabel () {
      return this.$t('tradingAgents.totalElapsed', { duration: this.formatDuration(this.progressTotalElapsedSeconds) })
    },
    progressHeartbeatLabel () {
      if (Number(this.progressSnapshot.heartbeat_count) > 0) return this.$t('tradingAgents.heartbeatLive')
      return this.$t('tradingAgents.waitingForGraph')
    },
    reportLocale () {
      return (this.run && this.run.language) || (this.isVietnamese ? 'vi-VN' : 'en-US')
    },
    reportLanguageLabel () {
      return this.$t(this.reportLocale === 'vi-VN' ? 'tradingAgents.reportLanguageVietnamese' : 'tradingAgents.reportLanguageEnglish')
    },
    reportDate () {
      const value = (this.run && (this.run.finished_at || this.run.created_at)) || this.analysisDate
      return value ? this.formatDateTime(value) : this.$t('tradingAgents.unavailable')
    },
    title () { return `${this.$t('tradingAgents.title')} · ${this.targetLabel}` }
  },
  watch: {
    visible (isVisible) {
      if (isVisible) {
        if (this.run) this.restorePolling()
        else this.loadLatestRun({ autoStart: true })
      } else {
        this.historyRequestId++
        this.stopPolling()
      }
    },
    target () {
      if (!this.visible) return
      this.historyRequestId++
      this.run = null
      this.reportContent = ''
      this.errorMessage = ''
      this.stopPolling()
      this.loadLatestRun({ autoStart: true })
    },
    reportContent () {
      this.resetReportSections()
    }
  },
  beforeDestroy () {
    this.stopPolling()
  },
  methods: {
    unwrap (response) { return response && response.data ? response.data : response },
    formatDateTime (value) {
      return formatVietnamDateTime(value, { locale: this.isVietnamese ? 'vi-VN' : 'en-GB', fallback: String(value || '') })
    },
    localizeHeading (value) {
      return localizeTradingAgentsHeading(value, this.reportLocale)
    },
    reportSectionIcon (title) {
      const text = String(title || '').toLowerCase()
      if (text.includes('risk') || text.includes('rủi ro')) return 'safety-certificate'
      if (text.includes('trading') || text.includes('giao dịch')) return 'line-chart'
      if (text.includes('decision') || text.includes('quyết định')) return 'check-circle'
      if (text.includes('analyst') || text.includes('phân tích')) return 'bar-chart'
      return 'file-text'
    },
    isReportSectionOpen (index) {
      return Boolean(this.openReportSections[index])
    },
    toggleReportSection (index) {
      this.$set(this.openReportSections, index, !this.isReportSectionOpen(index))
    },
    resetReportSections () {
      const openSections = {}
      this.reportSections.forEach((section, index) => {
        openSections[index] = index === 0
      })
      this.openReportSections = openSections
    },
    formatDuration (seconds) {
      const value = Math.max(0, Number(seconds) || 0)
      const minutes = Math.floor(value / 60)
      const remainder = Math.floor(value % 60)
      return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
    },
    async start () {
      if (!this.isSupported || this.starting) return
      const requestId = this.historyRequestId
      this.starting = true
      this.errorMessage = ''
      this.historyError = ''
      this.reportContent = ''
      try {
        const response = await createTradingAgentsRun({
          market: this.normalizedTarget.market,
          symbol: this.normalizedTarget.symbol,
          analysisDate: this.analysisDate || this.vietnamToday,
          language: this.isVietnamese ? 'vi-VN' : 'en-US',
          selectedAnalysts: FULL_ANALYSTS
        })
        const data = this.unwrap(response)
        if (!data || !data.run_id) throw new Error(this.$t('tradingAgents.startFailed'))
        if (requestId !== this.historyRequestId || !this.visible) return
        this.run = {
          run_id: data.run_id,
          status: data.status || 'queued',
          events: [],
          progress: {
            percent: 0,
            current_stage_id: 'initializing',
            stage_ids: this.progressStageIds,
            completed_stage_ids: [],
            completed_count: 0,
            total_count: this.progressStageIds.length
          }
        }
        this.startPolling()
      } catch (error) {
        this.errorMessage = (error && error.backendMessage) || (error && error.message) || this.$t('tradingAgents.startFailed')
      } finally {
        this.starting = false
      }
    },
    async refreshRun () {
      if (!this.run || !this.run.run_id) return
      const runId = this.run.run_id
      try {
        const data = this.unwrap(await getTradingAgentsRun(runId))
        if (!data || !data.run_id) throw new Error(this.$t('tradingAgents.loadFailed'))
        if (!this.visible || !this.run || this.run.run_id !== runId) return
        this.run = data
        if (String(data.status || '').toLowerCase() === 'succeeded') await this.loadReport(data)
        if (TERMINAL.has(String(data.status || '').toLowerCase())) this.stopPolling()
      } catch (error) {
        this.errorMessage = (error && error.backendMessage) || (error && error.message) || this.$t('tradingAgents.loadFailed')
        this.stopPolling()
      }
    },
    async loadLatestRun ({ autoStart = false } = {}) {
      if (!this.visible || !this.isSupported) return
      const requestId = ++this.historyRequestId
      const deadline = Date.now() + HISTORY_TIMEOUT_MS
      this.historyLoading = true
      this.errorMessage = ''
      this.historyError = ''
      try {
        const data = this.unwrap(await getTradingAgentsRuns({
          market: this.normalizedTarget.market,
          symbol: this.normalizedTarget.symbol,
          analysisDate: this.analysisDate || this.vietnamToday,
          limit: 1
        }, HISTORY_TIMEOUT_MS))
        if (requestId !== this.historyRequestId || !this.visible) return
        const summaries = Array.isArray(data && data.runs) ? data.runs : []
        if (!summaries.length || !summaries[0].run_id) {
          this.historyLoading = false
          if (autoStart) await this.start()
          return
        }
        const remaining = Math.max(1000, deadline - Date.now())
        const detail = this.unwrap(await getTradingAgentsRun(summaries[0].run_id, remaining))
        if (requestId !== this.historyRequestId || !this.visible || !detail || !detail.run_id) return
        this.run = detail
        this.restorePolling()
      } catch (error) {
        if (requestId === this.historyRequestId && this.visible) {
          this.historyError = (error && error.backendMessage) || (error && error.message) || this.$t('tradingAgents.historyLoadFailed')
        }
      } finally {
        if (requestId === this.historyRequestId) this.historyLoading = false
      }
    },
    async loadReport (run) {
      if (this.reportContent) return
      const artifact = Array.isArray(run.artifacts) ? run.artifacts.find(item => item && item.artifact_name) : null
      if (!artifact) return
      const runId = run.run_id
      try {
        const response = await getTradingAgentsArtifact(runId, artifact.artifact_name)
        if (!this.visible || !this.run || this.run.run_id !== runId) return
        this.reportContent = typeof response === 'string' ? response : String((response && response.data) || '')
      } catch (error) {
        this.errorMessage = (error && error.backendMessage) || (error && error.message) || this.$t('tradingAgents.reportLoadFailed')
      }
    },
    startPolling () {
      this.stopPolling()
      this.progressClock = Date.now()
      this.progressTimer = window.setInterval(() => { this.progressClock = Date.now() }, 1000)
      this.refreshRun()
      this.pollTimer = window.setInterval(() => this.refreshRun(), 2500)
    },
    restorePolling () {
      if (this.isRunning) this.startPolling()
      else if (this.run && String(this.run.status || '').toLowerCase() === 'succeeded') this.loadReport(this.run)
    },
    stopPolling () {
      if (this.pollTimer) window.clearInterval(this.pollTimer)
      if (this.progressTimer) window.clearInterval(this.progressTimer)
      this.pollTimer = null
      this.progressTimer = null
    },
    async cancel () {
      if (!this.run || this.cancelling) return
      this.cancelling = true
      try {
        await cancelTradingAgentsRun(this.run.run_id)
        this.run = { ...this.run, status: 'cancelled' }
        this.stopPolling()
      } catch (error) {
        this.errorMessage = (error && error.backendMessage) || (error && error.message) || this.$t('tradingAgents.cancelFailed')
      } finally {
        this.cancelling = false
      }
    },
    async resume () {
      if (!this.run || this.resuming) return
      this.resuming = true
      this.errorMessage = ''
      try {
        await resumeTradingAgentsRun(this.run.run_id)
        this.run = { ...this.run, status: 'queued' }
        this.startPolling()
      } catch (error) {
        this.errorMessage = (error && error.backendMessage) || (error && error.message) || this.$t('tradingAgents.resumeFailed')
      } finally {
        this.resuming = false
      }
    },
    async clearCheckpoint () {
      if (!this.run || this.clearing) return
      this.clearing = true
      try {
        await clearTradingAgentsCheckpoint(this.run.run_id)
        this.$message.success(this.$t('tradingAgents.checkpointCleared'))
      } catch (error) {
        this.errorMessage = (error && error.backendMessage) || (error && error.message) || this.$t('tradingAgents.clearFailed')
      } finally {
        this.clearing = false
      }
    },
    startFresh () {
      this.run = null
      this.reportContent = ''
      this.errorMessage = ''
      this.historyError = ''
      this.stopPolling()
    },
    close () {
      if (this.isRunning) return
      this.$emit('close')
    }
  }
}
</script>

<style lang="less" scoped>
.deep-analysis-panel { color: var(--ink, #1f2d3d); }
.deep-analysis-context { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 4px 0 16px; }
.deep-analysis-kicker { display: inline-flex; align-items: center; gap: 6px; color: var(--blue, #2563eb); font-size: 12px; font-weight: 700; }
.deep-analysis-context h3 { margin: 6px 0 4px; color: var(--ink, #1f2d3d); font-size: 20px; }
.deep-analysis-context p { max-width: 620px; margin: 0; color: var(--muted, #61738b); font-size: 13px; line-height: 1.55; }
.deep-analysis-provenance { display: flex; flex: 0 0 auto; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }.deep-analysis-provenance .ant-tag { margin: 0; }
.deep-analysis-empty { display: grid; justify-items: center; gap: 9px; min-height: 260px; padding: 40px 24px; text-align: center; }.deep-analysis-empty > .anticon { color: var(--blue, #2563eb); font-size: 38px; }.deep-analysis-empty h4 { margin: 4px 0 0; color: var(--ink, #1f2d3d); font-size: 17px; }.deep-analysis-empty p { max-width: 540px; margin: 0 0 8px; color: var(--muted, #61738b); line-height: 1.55; }
.deep-analysis-status-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 8px 0 12px; }.run-state { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; }.run-state--queued, .run-state--running { color: #2563eb; }.run-state--succeeded { color: #16865a; }.run-state--failed, .run-state--cancelled { color: #bd4d4d; }.run-time { color: var(--muted, #61738b); font-size: 12px; }
.deep-analysis-progress { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 10px 16px; padding: 15px; border: 1px solid var(--line, #dbe4ef); border-radius: 10px; background: var(--soft-blue, #f5f9ff); }.deep-analysis-progress .ant-progress { grid-column: 1 / -1; margin: 0; }.progress-copy { display: grid; gap: 3px; min-width: 0; }.progress-copy strong { font-size: 13px; }.progress-copy span { color: var(--muted, #61738b); font-size: 12px; }.progress-copy .progress-current { display: inline-flex; align-items: center; gap: 5px; color: var(--blue, #2563eb); font-weight: 600; }.deep-analysis-stage-list { display: flex; grid-column: 1 / -1; flex-wrap: wrap; gap: 6px; padding-top: 3px; }.deep-analysis-stage { display: inline-flex; align-items: center; gap: 4px; padding: 4px 7px; border: 1px solid var(--line, #dbe4ef); border-radius: 999px; color: var(--muted, #61738b); font-size: 11px; line-height: 1.25; }.deep-analysis-stage.is-complete { border-color: #b7e3cf; color: #16865a; background: #f0fbf5; }.deep-analysis-stage.is-current { border-color: #9fc2ff; color: #245dcc; background: #eef5ff; }.history-recovery-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
.deep-analysis-recovery { display: grid; gap: 10px; }.recovery-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.deep-analysis-report { margin-top: 14px; overflow: hidden; border: 1px solid var(--line, #dbe4ef); border-radius: 10px; background: var(--card, #fff); }.report-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px 15px; border-bottom: 1px solid var(--line, #dbe4ef); }.report-heading h4 { margin: 0; color: var(--ink, #1f2d3d); font-size: 15px; }.report-heading span { display: block; margin-top: 2px; color: var(--muted, #61738b); font-size: 11px; }.report-heading .ant-tag { margin: 0; }.deep-analysis-report pre { max-height: 52vh; margin: 0; overflow: auto; padding: 16px; color: var(--ink, #1f2d3d); background: transparent; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }.deep-analysis-history-loading, .deep-analysis-report-loading { display: flex; align-items: center; gap: 8px; min-height: 110px; color: var(--muted, #61738b); }.deep-analysis-error { margin-bottom: 12px; }
.deep-analysis-footer { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--line, #dbe4ef); color: var(--muted, #61738b); font-size: 12px; line-height: 1.45; }.deep-analysis-footer span { display: inline-flex; align-items: flex-start; gap: 6px; }
.deep-analysis-report { border-radius: 12px; }.report-heading { align-items: flex-start; padding: 16px 18px; background: var(--soft-blue, #f5f9ff); }.report-heading-copy { min-width: 0; }.report-eyebrow { display: inline-flex !important; align-items: center; gap: 6px; margin: 0 0 5px !important; color: var(--blue, #2563eb) !important; font-size: 11px !important; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }.report-heading h4 { margin: 0; color: var(--ink, #1f2d3d); font-size: 19px; letter-spacing: -.01em; }.report-heading-copy > span:last-child { display: block; margin-top: 5px; color: var(--muted, #61738b); font-size: 12px; line-height: 1.45; }.report-heading-tags { display: flex; flex: 0 0 auto; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }.report-heading .ant-tag { margin: 0; }.report-meta-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; border-bottom: 1px solid var(--line, #dbe4ef); background: var(--line, #dbe4ef); }.report-meta-grid > div { display: grid; gap: 4px; min-width: 0; padding: 10px 14px; background: var(--card, #fff); }.report-meta-grid span { color: var(--muted, #61738b); font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }.report-meta-grid strong { overflow: hidden; color: var(--ink, #1f2d3d); font-size: 12px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }.report-body { max-height: 52vh; overflow: auto; padding: 6px 18px 18px; }.report-block { color: var(--ink, #1f2d3d); }.report-block--heading { margin-top: 14px; }.report-block h5 { margin: 0; color: var(--ink, #1f2d3d); font-size: 13px; line-height: 1.4; }.report-block-title { padding: 10px 0 7px; border-bottom: 1px solid var(--line, #dbe4ef); color: var(--blue, #245dcc) !important; font-size: 15px !important; }.report-block--paragraph p { margin: 8px 0; color: var(--text-secondary, #4f6380); font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }.report-list { display: grid; gap: 7px; margin: 9px 0 12px; padding: 0 0 0 19px; color: var(--text-secondary, #4f6380); font-size: 13px; line-height: 1.6; }.report-list li::marker { color: var(--blue, #2563eb); }.report-empty { padding: 22px 0; color: var(--muted, #61738b); font-size: 13px; }
@media (max-width: 640px) { .deep-analysis-context { flex-direction: column; gap: 10px; }.deep-analysis-context h3 { font-size: 18px; }.deep-analysis-provenance { justify-content: flex-start; }.deep-analysis-empty { min-height: 230px; padding: 28px 12px; }.deep-analysis-status-row { align-items: flex-start; flex-direction: column; }.deep-analysis-progress { grid-template-columns: 1fr; }.deep-analysis-progress .ant-btn { width: 100%; min-height: 44px; }.deep-analysis-stage-list { display: grid; grid-template-columns: 1fr; }.deep-analysis-stage { min-height: 32px; }.history-recovery-actions { display: grid; grid-template-columns: 1fr; width: 100%; }.history-recovery-actions .ant-btn { min-height: 44px; }.recovery-actions { display: grid; grid-template-columns: 1fr; }.recovery-actions .ant-btn { min-height: 44px; }.report-heading { align-items: flex-start; flex-direction: column; }.deep-analysis-report pre { max-height: 48vh; padding: 13px; font-size: 11px; }.deep-analysis-footer { align-items: stretch; flex-direction: column; }.deep-analysis-footer .ant-btn { min-height: 44px; } }
</style>

<style lang="less">
.trading-agents-modal .deep-analysis-progress {
  display: block;
  padding: 18px;
  border: 1px solid var(--line, #dbe4ef);
  border-radius: 14px;
  background: linear-gradient(145deg, var(--soft-blue, #f5f9ff), var(--card, #fff));
}

.trading-agents-modal .progress-topline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.trading-agents-modal .progress-title {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 3px 8px;
  min-width: 0;
}

.trading-agents-modal .progress-title strong {
  min-width: 0;
  color: var(--ink, #1f2d3d);
  font-size: 14px;
  line-height: 1.35;
}

.trading-agents-modal .progress-title > span:last-child {
  grid-column: 2;
  color: var(--muted, #61738b);
  font-size: 12px;
}

.trading-agents-modal .progress-live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #20a464;
  box-shadow: 0 0 0 4px rgba(32, 164, 100, .12);
}

.trading-agents-modal .progress-percent {
  flex: 0 0 auto;
  color: var(--blue, #2563eb);
  font-size: 24px;
  line-height: 1;
}

.trading-agents-modal .deep-analysis-progress > .ant-progress {
  display: block;
  margin: 16px 0;
}

.trading-agents-modal .progress-current-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 13px;
  border: 1px solid rgba(37, 99, 235, .16);
  border-radius: 10px;
  background: rgba(255, 255, 255, .72);
}

.trading-agents-modal .progress-current-icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  color: #2563eb;
  background: #eaf2ff;
  font-size: 16px;
}

.trading-agents-modal .progress-current-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.trading-agents-modal .progress-current-label {
  color: var(--muted, #61738b);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .07em;
  text-transform: uppercase;
}

.trading-agents-modal .progress-current-copy strong {
  color: var(--ink, #1f2d3d);
  font-size: 14px;
}

.trading-agents-modal .progress-current-copy p {
  margin: 2px 0 0;
  color: var(--muted, #61738b);
  font-size: 12px;
  line-height: 1.45;
}

.trading-agents-modal .progress-time {
  display: grid;
  justify-items: end;
  gap: 3px;
  min-width: 68px;
}

.trading-agents-modal .progress-time strong {
  color: var(--ink, #1f2d3d);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 16px;
}

.trading-agents-modal .progress-time span,
.trading-agents-modal .progress-footnote {
  color: var(--muted, #61738b);
  font-size: 11px;
}

.trading-agents-modal .progress-footnote {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
}

.trading-agents-modal .progress-footnote .anticon {
  color: #20a464;
}

.trading-agents-modal .progress-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.trading-agents-modal .deep-analysis-stage-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--line, #dbe4ef);
}

.trading-agents-modal .deep-analysis-stage {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 8px 9px;
  border: 1px solid var(--line, #dbe4ef);
  border-radius: 9px;
  color: var(--muted, #61738b);
  background: rgba(255, 255, 255, .5);
}

.trading-agents-modal .deep-analysis-stage-marker {
  display: grid;
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  place-items: center;
  border-radius: 50%;
  color: #8b9ab0;
  background: #eef2f7;
  font-size: 10px;
}

.trading-agents-modal .deep-analysis-stage-copy {
  display: grid;
  gap: 1px;
  min-width: 0;
}

.trading-agents-modal .deep-analysis-stage-copy small {
  color: #93a1b4;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 9px;
}

.trading-agents-modal .deep-analysis-stage-copy > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

.trading-agents-modal .deep-analysis-stage.is-complete {
  border-color: #b9e7cf;
  color: #16865a;
  background: #f1fbf5;
}

.trading-agents-modal .deep-analysis-stage.is-complete .deep-analysis-stage-marker {
  color: #fff;
  background: #20a464;
}

.trading-agents-modal .deep-analysis-stage.is-current {
  border-color: #a8c7ff;
  color: #245dcc;
  background: #eef5ff;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, .06);
}

.trading-agents-modal .deep-analysis-stage.is-current .deep-analysis-stage-marker {
  color: #245dcc;
  background: #dceaff;
}

.trading-agents-modal .report-body {
  max-height: 58vh;
  padding: 16px 18px 20px;
  background: var(--card, #fff);
}

.trading-agents-modal .report-sections {
  display: grid;
  gap: 12px;
}

.trading-agents-modal .report-section {
  overflow: hidden;
  border: 1px solid var(--line, #dbe4ef);
  border-radius: 12px;
  background: var(--card, #fff);
}

.trading-agents-modal .report-section-heading {
  appearance: none;
  width: 100%;
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 12px 14px;
  border: 0;
  border-bottom: 1px solid var(--line, #dbe4ef);
  background: linear-gradient(90deg, var(--soft-blue, #f5f9ff), var(--card, #fff));
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background .18s ease, box-shadow .18s ease;
}

.trading-agents-modal .report-section:not(.is-open) .report-section-heading {
  border-bottom: 0;
}

.trading-agents-modal .report-section-heading:hover {
  background: linear-gradient(90deg, #eef5ff, var(--card, #fff));
}

.trading-agents-modal .report-section-heading:focus-visible {
  outline: 2px solid var(--blue, #2563eb);
  outline-offset: -2px;
}

.trading-agents-modal .report-section-number {
  color: #91a1b6;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 10px;
  font-weight: 700;
}

.trading-agents-modal .report-section-icon {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  color: var(--blue, #2563eb);
  background: #eaf2ff;
}

.trading-agents-modal .report-section-heading-copy {
  min-width: 0;
}

.trading-agents-modal .report-section-heading h5 {
  overflow: hidden;
  margin: 0;
  color: var(--ink, #1f2d3d);
  font-size: 14px;
  text-overflow: ellipsis;
  line-height: 1.35;
  white-space: nowrap;
}

.trading-agents-modal .report-section-chevron {
  margin-left: auto;
  color: var(--muted, #61738b);
  font-size: 12px;
  transition: transform .18s ease, color .18s ease;
}

.trading-agents-modal .report-section-heading:hover .report-section-chevron {
  color: var(--blue, #2563eb);
}

.trading-agents-modal .report-section-content {
  padding: 10px 14px 14px;
}

.trading-agents-modal .report-block + .report-block {
  margin-top: 10px;
}

.trading-agents-modal .report-block--heading h6 {
  margin: 0 0 6px;
  color: var(--ink, #1f2d3d);
  font-size: 13px;
  line-height: 1.4;
}

.trading-agents-modal .report-block--paragraph p {
  margin: 0;
  color: var(--text-secondary, #4f6380);
  font-size: 13px;
  line-height: 1.72;
}

.trading-agents-modal .report-list {
  display: grid;
  gap: 7px;
  margin: 0;
  padding-left: 19px;
  color: var(--text-secondary, #4f6380);
  font-size: 13px;
  line-height: 1.6;
}

.trading-agents-modal .report-list li::marker {
  color: #20a464;
}

.trading-agents-modal .report-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--line, #dbe4ef);
  border-radius: 9px;
}

.trading-agents-modal .report-table {
  width: 100%;
  min-width: 360px;
  border-collapse: collapse;
  color: var(--text-secondary, #4f6380);
  font-size: 12px;
}

.trading-agents-modal .report-table th,
.trading-agents-modal .report-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line, #dbe4ef);
  text-align: left;
  vertical-align: top;
}

.trading-agents-modal .report-table th {
  color: var(--ink, #1f2d3d);
  background: var(--soft-blue, #f5f9ff);
  font-size: 11px;
  font-weight: 700;
}

.trading-agents-modal .report-table tr:last-child td {
  border-bottom: 0;
}

.trading-agents-modal .theme-dark .progress-title strong,
.trading-agents-modal .theme-dark .progress-current-copy strong,
.trading-agents-modal .theme-dark .progress-time strong,
.trading-agents-modal .theme-dark .report-section-heading h5,
.trading-agents-modal .theme-dark .report-block--heading h6,
.trading-agents-modal .theme-dark .report-table th {
  color: #e6edf6;
}

.trading-agents-modal .theme-dark .progress-current-card,
.trading-agents-modal .theme-dark .deep-analysis-stage {
  background: rgba(24, 32, 44, .72);
}

.trading-agents-modal .theme-dark .report-section,
.trading-agents-modal .theme-dark .report-body {
  background: #18202c;
}

.trading-agents-modal .theme-dark .report-section-heading,
.trading-agents-modal .theme-dark .report-table th {
  background: #152334;
}

.trading-agents-modal .theme-dark .report-section-icon,
.trading-agents-modal .theme-dark .progress-current-icon {
  background: #20385c;
}

.trading-agents-modal .theme-dark .report-section-heading:hover {
  background: linear-gradient(90deg, #1b3150, #18202c);
}

@media (max-width: 640px) {
  .trading-agents-modal .deep-analysis-progress {
    padding: 14px;
  }

  .trading-agents-modal .progress-topline {
    gap: 10px;
  }

  .trading-agents-modal .progress-title strong {
    font-size: 13px;
  }

  .trading-agents-modal .progress-percent {
    font-size: 21px;
  }

  .trading-agents-modal .progress-current-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .trading-agents-modal .progress-time {
    grid-column: 2;
    justify-items: start;
    grid-template-columns: auto auto;
    align-items: baseline;
    gap: 8px;
  }

  .trading-agents-modal .deep-analysis-stage-list {
    grid-template-columns: 1fr;
  }

  .trading-agents-modal .report-body {
    padding: 12px 12px 16px;
  }

  .trading-agents-modal .report-section-heading {
    grid-template-columns: auto auto minmax(0, 1fr) auto;
    padding: 11px 12px;
  }

  .trading-agents-modal .report-section-content {
    padding: 10px 12px 12px;
  }

  .trading-agents-modal .report-block--paragraph p,
  .trading-agents-modal .report-list {
    font-size: 12px;
  }
}
</style>

<style lang="less">
.trading-agents-modal .ant-modal { max-width: calc(100vw - 24px); padding-bottom: 0; }.trading-agents-modal .ant-modal-body { max-height: calc(100dvh - 132px); overflow: auto; padding: 20px 22px; }.trading-agents-modal .theme-dark { color: #e6edf6; }.trading-agents-modal .theme-dark .deep-analysis-context h3, .trading-agents-modal .theme-dark .deep-analysis-empty h4, .trading-agents-modal .theme-dark .report-heading h4, .trading-agents-modal .theme-dark .report-meta-grid strong, .trading-agents-modal .theme-dark .report-block h5 { color: #e6edf6; }.trading-agents-modal .theme-dark .deep-analysis-report { background: #18202c; border-color: #334155; }.trading-agents-modal .theme-dark .deep-analysis-progress { background: #152334; border-color: #334155; }.trading-agents-modal .theme-dark .report-heading { background: #152334; border-color: #334155; }.trading-agents-modal .theme-dark .report-meta-grid { background: #334155; border-color: #334155; }.trading-agents-modal .theme-dark .report-meta-grid > div { background: #18202c; }.trading-agents-modal .theme-dark .report-block--paragraph p, .trading-agents-modal .theme-dark .report-list { color: #b6c3d6; }.trading-agents-modal .theme-dark .report-block-title, .trading-agents-modal .theme-dark .deep-analysis-footer { border-color: #334155; }
@media (max-width: 640px) { .trading-agents-modal .ant-modal { top: 12px; margin: 0 auto; }.trading-agents-modal .ant-modal-body { max-height: calc(100dvh - 70px); padding: 16px 14px; }.trading-agents-modal .report-heading { flex-direction: column; gap: 10px; padding: 14px; }.trading-agents-modal .report-heading-tags { justify-content: flex-start; }.trading-agents-modal .report-heading h4 { font-size: 17px; }.trading-agents-modal .report-meta-grid { grid-template-columns: 1fr; }.trading-agents-modal .report-meta-grid > div { padding: 9px 14px; }.trading-agents-modal .report-body { max-height: 48vh; padding: 4px 14px 15px; }.trading-agents-modal .report-block--paragraph p, .trading-agents-modal .report-list { font-size: 12px; } }
</style>
