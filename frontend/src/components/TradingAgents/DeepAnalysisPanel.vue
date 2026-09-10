<template>
  <a-modal
    :visible="visible"
    :title="title"
    :width="960"
    :footer="null"
    centered
    :mask-closable="true"
    :keyboard="true"
    :wrap-class-name="dark ? 'trading-agents-modal trading-agents-modal--dark' : 'trading-agents-modal'"
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
          <a-button type="primary" :loading="historyLoading" @click="loadReportHistory">
            <a-icon type="reload" /> {{ $t('tradingAgents.historyRetry') }}
          </a-button>
        </div>
      </div>

      <div v-else-if="!run && isSupported" class="deep-analysis-empty">
        <template v-if="historyReports.length">
          <a-icon type="book" />
          <h4>{{ $t('tradingAgents.historyTitle') }}</h4>
          <p>{{ $t('tradingAgents.historyDescription') }}</p>
          <div class="report-history-list">
            <article v-for="report in historyReports" :key="report.run_id" class="report-history-item">
              <div><strong>{{ report.analysis_date }}</strong><span>{{ formatDateTime(report.finished_at || report.created_at) }}</span></div>
              <a-button size="small" :loading="historyReportOpening === report.run_id" @click="openHistoryReport(report)"><a-icon type="export" /> {{ $t('tradingAgents.openHistoryReport') }}</a-button>
            </article>
          </div>
        </template>
        <template v-else>
          <a-icon type="radar-chart" />
          <h4>{{ $t('tradingAgents.noHistoryTitle') }}</h4>
          <p>{{ $t('tradingAgents.noHistoryDescription') }}</p>
        </template>
        <a-alert v-if="todayRun" type="info" show-icon :message="$t('tradingAgents.todayRunExists')" class="today-run-notice" />
        <a-button v-if="!todayRun" type="primary" size="large" :loading="starting" @click="start">
          <a-icon type="thunderbolt" /> {{ $t('tradingAgents.start') }}
        </a-button>
        <a-button v-else-if="todayRun.status === 'succeeded'" :loading="historyReportOpening === todayRun.run_id" @click="openHistoryReport(todayRun)">
          <a-icon type="export" /> {{ $t('tradingAgents.openTodayReport') }}
        </a-button>
        <a-button v-else @click="viewTodayRun"><a-icon type="eye" /> {{ $t('tradingAgents.viewTodayRun') }}</a-button>
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
              <p v-if="progressSubstepLabel" class="progress-substep">
                <a-icon :type="progressSubstepStatus === 'completed' ? 'check-circle' : (progressSubstepStatus === 'failed' ? 'warning' : 'loading')" />
                {{ progressSubstepLabel }}
              </p>
            </div>
            <div class="progress-time">
              <strong>{{ progressElapsedLabel }}</strong>
              <span>{{ progressTotalElapsedLabel }}</span>
            </div>
          </div>
          <div class="progress-footnote">
            <a-icon type="sync" /> {{ progressHeartbeatLabel }}
          </div>
          <p class="progress-footnote">{{ $t('tradingAgents.canCloseRunning') }}</p>
          <a-alert v-if="pollError" type="warning" show-icon :message="$t('tradingAgents.reconnecting')" />
          <a-alert
            v-if="isLongRunning"
            type="warning"
            show-icon
            :message="$t('tradingAgents.longRunningTitle')"
            :description="$t('tradingAgents.longRunningDescription')"
            class="deep-analysis-long-running"
          />
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
          <a-alert type="warning" show-icon :message="$t('tradingAgents.interruptedTitle')" :description="$t(run.failure_code === 'provider_timeout' ? 'tradingAgents.providerTimeout' : 'tradingAgents.interruptedDescription')" />
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
              <h4 id="deep-analysis-report-title">{{ localizeHeading(reportDocumentTitle) }}</h4>
              <span>{{ $t('tradingAgents.reportProvenance') }}</span>
            </div>
            <div class="report-heading-tags">
              <a-tag color="blue"><a-icon type="global" /> {{ reportLanguageLabel }}</a-tag>
              <a-tag color="green"><a-icon type="safety-certificate" /> {{ $t('tradingAgents.researchOnly') }}</a-tag>
              <a-button size="small" :loading="exportingPdf" @click="exportReportPdf">
                <a-icon type="file-pdf" /> {{ $t('tradingAgents.exportPdf') }}
              </a-button>
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
                    <div v-else-if="block.type === 'callout'" class="report-callout" :class="`report-callout--${block.tone || 'info'}`">
                      <span>{{ block.label }}</span><strong>{{ block.value }}</strong>
                    </div>
                    <ul v-else-if="block.type === 'list'" class="report-list">
                      <li v-for="(item, itemIndex) in block.items" :key="`${sectionIndex}-${blockIndex}-${itemIndex}`">{{ item }}</li>
                    </ul>
                    <div v-else-if="block.type === 'table'" class="report-table-wrap">
                      <table class="report-table">
                        <thead><tr><th v-for="(header, headerIndex) in block.headers" :key="`${sectionIndex}-${blockIndex}-header-${headerIndex}`">{{ header }}</th></tr></thead>
                        <tbody><tr v-for="(row, rowIndex) in block.rows" :key="`${sectionIndex}-${blockIndex}-row-${rowIndex}`"><td v-for="(cell, cellIndex) in row" :key="`${sectionIndex}-${blockIndex}-${rowIndex}-${cellIndex}`">{{ cell }}</td></tr></tbody>
                      </table>
                    </div>
                    <pre v-else-if="block.type === 'code'">{{ block.text }}</pre>
                    <p v-else>{{ block.text }}</p>
                  </div>
                  <div v-if="section.subsections && section.subsections.length" class="report-subsections">
                    <article v-for="(subsection, subsectionIndex) in section.subsections" :key="`${sectionIndex}-${subsection.title}-${subsectionIndex}`" class="report-subsection" :class="{ 'is-open': isReportSubsectionOpen(sectionIndex, subsectionIndex) }">
                      <button
                        type="button"
                        class="report-subsection-heading"
                        :aria-expanded="isReportSubsectionOpen(sectionIndex, subsectionIndex)"
                        :aria-controls="`report-subsection-content-${sectionIndex}-${subsectionIndex}`"
                        :aria-label="$t('tradingAgents.toggleReportSection', { section: localizeHeading(subsection.title) })"
                        @click="toggleReportSubsection(sectionIndex, subsectionIndex)"
                      >
                        <span class="report-subsection-number">{{ sectionIndex + 1 }}.{{ subsectionIndex + 1 }}</span>
                        <span class="report-subsection-heading-copy"><h6>{{ localizeHeading(subsection.title) }}</h6></span>
                        <a-icon class="report-section-chevron" :type="isReportSubsectionOpen(sectionIndex, subsectionIndex) ? 'up' : 'down'" aria-hidden="true" />
                      </button>
                      <div
                        :id="`report-subsection-content-${sectionIndex}-${subsectionIndex}`"
                        v-show="isReportSubsectionOpen(sectionIndex, subsectionIndex)"
                        class="report-subsection-content"
                        :aria-hidden="!isReportSubsectionOpen(sectionIndex, subsectionIndex)"
                      >
                        <div v-for="(block, blockIndex) in subsection.blocks" :key="`${sectionIndex}-${subsectionIndex}-${block.type}-${blockIndex}`" class="report-block" :class="`report-block--${block.type}`">
                          <h6 v-if="block.type === 'heading'">{{ localizeHeading(block.text) }}</h6>
                          <div v-else-if="block.type === 'callout'" class="report-callout" :class="`report-callout--${block.tone || 'info'}`">
                            <span>{{ block.label }}</span><strong>{{ block.value }}</strong>
                          </div>
                          <ul v-else-if="block.type === 'list'" class="report-list">
                            <li v-for="(item, itemIndex) in block.items" :key="`${sectionIndex}-${subsectionIndex}-${blockIndex}-${itemIndex}`">{{ item }}</li>
                          </ul>
                          <div v-else-if="block.type === 'table'" class="report-table-wrap">
                            <table class="report-table">
                              <thead><tr><th v-for="(header, headerIndex) in block.headers" :key="`${sectionIndex}-${subsectionIndex}-${blockIndex}-header-${headerIndex}`">{{ header }}</th></tr></thead>
                              <tbody><tr v-for="(row, rowIndex) in block.rows" :key="`${sectionIndex}-${subsectionIndex}-${blockIndex}-row-${rowIndex}`"><td v-for="(cell, cellIndex) in row" :key="`${sectionIndex}-${subsectionIndex}-${rowIndex}-${cellIndex}`">{{ cell }}</td></tr></tbody>
                            </table>
                          </div>
                          <pre v-else-if="block.type === 'code'">{{ block.text }}</pre>
                          <p v-else>{{ block.text }}</p>
                        </div>
                        <report-branch v-for="(child, childIndex) in subsection.subsections" :key="childIndex" :section="child" :language="reportLocale" />
                      </div>
                    </article>
                  </div>
                </div>
              </article>
            </div>
            <div v-else class="report-empty">{{ $t('tradingAgents.reportEmpty') }}</div>
          </div>
        </section>
        <div v-else-if="run.status === 'succeeded'" class="deep-analysis-report-loading">
          <template v-if="reportError">
            <span>{{ $t('tradingAgents.reportLoadFailed') }}</span>
            <a-button @click="loadReport(run)">{{ $t('tradingAgents.retryReport') }}</a-button>
          </template>
          <template v-else><a-spin size="small" /> {{ $t('tradingAgents.loadingReport') }}</template>
        </div>
      </template>

      <div class="deep-analysis-footer">
        <span><a-icon type="info-circle" /> {{ $t('tradingAgents.disclaimer') }}</span>
        <a-button @click="close">{{ $t('tradingAgents.close') }}</a-button>
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
  getTradingAgentsReportPdf,
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
import { parseUtcAwareInstant } from '@/utils/utcInstant'
import ReportBranch from './ReportBranch.vue'

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
  components: { ReportBranch },
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
      pollGeneration: 0,
      pollingRequest: null,
      pollError: false,
      reportError: false,
      reportRequest: null,
      exportingPdf: false,
      progressTimer: null,
      progressClock: Date.now(),
      historyLoading: false,
      historyRequestId: 0,
      historyError: '',
      historyReports: [],
      todayRun: null,
      historyReportOpening: '',
      openReportSections: {},
      openReportSubsections: {}
    }
  },
  computed: {
    vietnamToday () { return vietnamDay() },
    contextKey () { return `${this.normalizedTarget.market}:${this.normalizedTarget.symbol}:${this.analysisDate || this.vietnamToday}:${this.$i18n.locale}` },
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
    progressSubstepLabel () {
      const substepId = this.progressSnapshot.current_substep_id
      return substepId ? this.$t(`tradingAgents.substeps.${substepId}`) : ''
    },
    progressSubstepStatus () {
      return String(this.progressSnapshot.current_substep_status || '')
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
    reportDocument () {
      return groupTradingAgentsReportSections(this.reportBlocks)
    },
    reportDocumentTitle () {
      return this.reportDocument.title || this.targetLabel
    },
    reportSections () {
      return this.reportDocument.sections
    },
    progressElapsedSeconds () {
      const reported = Number(this.progressSnapshot.elapsed_seconds) || 0
      const startedAt = Number(parseUtcAwareInstant(this.progressSnapshot.stage_started_at)) || NaN
      if (!this.isRunning || !Number.isFinite(startedAt)) return reported
      return Math.max(reported, Math.floor((this.progressClock - startedAt) / 1000))
    },
    progressTotalElapsedSeconds () {
      const reported = Number(this.progressSnapshot.total_elapsed_seconds) || 0
      const startedAt = Number(parseUtcAwareInstant(this.run && this.run.started_at)) || NaN
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
      const lastEvent = Number(parseUtcAwareInstant(this.progressSnapshot.last_event_at)) || 0
      if (this.pollError || (lastEvent && this.progressClock - lastEvent > 30000)) return this.$t('tradingAgents.progressDelayed')
      if (Number(this.progressSnapshot.heartbeat_count) > 0) return this.$t('tradingAgents.heartbeatLive')
      return this.$t('tradingAgents.waitingForGraph')
    },
    isLongRunning () {
      return this.isRunning && this.progressElapsedSeconds >= 180
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
        else this.loadReportHistory()
      } else {
        this.historyRequestId++
        this.stopPolling()
      }
    },
    contextKey () {
      this.historyRequestId++
      this.run = null
      this.reportContent = ''
      this.reportRequest = null
      this.reportError = false
      this.errorMessage = ''
      this.historyReports = []
      this.todayRun = null
      this.stopPolling()
      if (this.visible) this.loadReportHistory()
    },
    reportContent () {
      this.resetReportSections()
    }
  },
  beforeDestroy () {
    this.historyRequestId++
    this.stopPolling()
  },
  methods: {
    unwrap (response) { return response && response.data ? response.data : response },
    isCurrentRun (runId, requestId) {
      return this.visible && requestId === this.historyRequestId && this.run && this.run.run_id === runId
    },
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
    reportSubsectionKey (sectionIndex, subsectionIndex) {
      return `${sectionIndex}:${subsectionIndex}`
    },
    isReportSubsectionOpen (sectionIndex, subsectionIndex) {
      return Boolean(this.openReportSubsections[this.reportSubsectionKey(sectionIndex, subsectionIndex)])
    },
    toggleReportSubsection (sectionIndex, subsectionIndex) {
      const key = this.reportSubsectionKey(sectionIndex, subsectionIndex)
      this.$set(this.openReportSubsections, key, !this.isReportSubsectionOpen(sectionIndex, subsectionIndex))
    },
    resetReportSections () {
      const openSections = {}
      const openSubsections = {}
      this.reportSections.forEach((section, index) => {
        openSections[index] = index === 0
        const subsections = section.subsections || []
        subsections.forEach((subsection, subsectionIndex) => {
          openSubsections[this.reportSubsectionKey(index, subsectionIndex)] = index === 0 && subsectionIndex === 0
        })
      })
      this.openReportSections = openSections
      this.openReportSubsections = openSubsections
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
          analysisDate: this.vietnamToday,
          language: this.isVietnamese ? 'vi-VN' : 'en-US',
          selectedAnalysts: FULL_ANALYSTS
        })
        const data = this.unwrap(response)
        if (!data || !data.run_id) throw new Error(this.$t('tradingAgents.startFailed'))
        if (requestId !== this.historyRequestId || !this.visible) return
        if (data.daily_limit_reached) {
          this.todayRun = { run_id: data.run_id, status: data.status || 'queued', analysis_date: this.vietnamToday }
          await this.loadReportHistory()
          return
        }
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
        if (requestId === this.historyRequestId && this.visible) this.errorMessage = this.$t('tradingAgents.startFailed')
      } finally {
        this.starting = false
      }
    },
    async refreshRun () {
      if (!this.run || !this.run.run_id) return
      const runId = this.run.run_id
      const generation = this.pollGeneration
      if (this.pollingRequest === generation) return
      this.pollingRequest = generation
      try {
        const data = this.unwrap(await getTradingAgentsRun(runId, HISTORY_TIMEOUT_MS))
        if (!data || !data.run_id) throw new Error(this.$t('tradingAgents.loadFailed'))
        if (generation !== this.pollGeneration || !this.visible || !this.run || this.run.run_id !== runId) return
        this.pollError = false
        this.run = data
        if (String(data.status || '').toLowerCase() === 'succeeded') await this.loadReport(data)
        if (TERMINAL.has(String(data.status || '').toLowerCase())) this.stopPolling()
      } catch (error) {
        if (generation === this.pollGeneration && this.visible) this.pollError = true
      } finally {
        if (this.pollingRequest === generation) this.pollingRequest = null
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
          this.historyError = this.$t('tradingAgents.historyLoadFailed')
        }
      } finally {
        if (requestId === this.historyRequestId) this.historyLoading = false
      }
    },
    async loadReportHistory () {
      if (!this.visible || !this.isSupported) return
      const requestId = ++this.historyRequestId
      this.historyLoading = true
      this.historyError = ''
      try {
        const data = this.unwrap(await getTradingAgentsRuns({
          market: this.normalizedTarget.market,
          symbol: this.normalizedTarget.symbol,
          scope: 'history',
          limit: 100
        }, HISTORY_TIMEOUT_MS))
        if (requestId !== this.historyRequestId || !this.visible) return
        this.historyReports = Array.isArray(data && data.runs) ? data.runs : []
        this.todayRun = data && data.today_run ? data.today_run : null
      } catch (error) {
        if (requestId === this.historyRequestId && this.visible) this.historyError = this.$t('tradingAgents.historyLoadFailed')
      } finally {
        if (requestId === this.historyRequestId) this.historyLoading = false
      }
    },
    async loadReport (run) {
      if (this.reportContent) return
      const requestId = this.historyRequestId
      const requestKey = `${requestId}:${run.run_id}`
      if (this.reportRequest === requestKey) return
      this.reportError = false
      const artifact = Array.isArray(run.artifacts) ? run.artifacts.find(item => item && item.artifact_name) : null
      if (!artifact) { this.reportError = true; return }
      this.reportRequest = requestKey
      const runId = run.run_id
      try {
        const response = await getTradingAgentsArtifact(runId, artifact.artifact_name)
        if (requestId !== this.historyRequestId || !this.visible || !this.run || this.run.run_id !== runId) return
        this.reportContent = typeof response === 'string' ? response : String((response && response.data) || '')
        if (!this.reportContent.trim()) this.reportError = true
      } catch (error) {
        if (requestId === this.historyRequestId && this.visible) this.reportError = true
      } finally {
        if (this.reportRequest === requestKey) this.reportRequest = null
      }
    },
    async exportReportPdf () {
      if (!this.run || !this.run.run_id || this.exportingPdf) return
      const preview = window.open('', '_blank')
      this.writePdfLoadingPreview(preview)
      this.exportingPdf = true
      try {
        const response = await getTradingAgentsReportPdf(this.run.run_id)
        const blob = response instanceof Blob ? response : new Blob([response && response.data ? response.data : response], { type: 'application/pdf' })
        const url = window.URL.createObjectURL(blob)
        if (preview) {
          preview.opener = null
          preview.location.href = url
        } else {
          window.open(url, '_blank', 'noopener')
        }
        const link = document.createElement('a')
        link.href = url
        link.download = this.reportPdfFilename()
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.setTimeout(() => window.URL.revokeObjectURL(url), 60000)
      } catch (error) {
        if (preview) preview.close()
        this.$message.error(this.$t('tradingAgents.pdfExportFailed'))
      } finally {
        this.exportingPdf = false
      }
    },
    async openHistoryReport (report) {
      if (!report || !report.run_id || this.historyReportOpening) return
      const preview = window.open('', '_blank')
      this.writePdfLoadingPreview(preview)
      this.historyReportOpening = report.run_id
      try {
        const response = await getTradingAgentsReportPdf(report.run_id)
        const blob = response instanceof Blob ? response : new Blob([response && response.data ? response.data : response], { type: 'application/pdf' })
        const url = window.URL.createObjectURL(blob)
        if (preview) {
          preview.opener = null
          preview.location.href = url
        } else window.open(url, '_blank', 'noopener')
        window.setTimeout(() => window.URL.revokeObjectURL(url), 60000)
      } catch (error) {
        if (preview) preview.close()
        this.$message.error(this.$t('tradingAgents.historyOpenFailed'))
      } finally {
        this.historyReportOpening = ''
      }
    },
    viewTodayRun () {
      if (!this.todayRun) return
      this.run = this.todayRun
      this.restorePolling()
    },
    writePdfLoadingPreview (preview) {
      if (!preview || !preview.document) return
      const escapeHtml = (value) => String(value || '').replace(/[&<>'"]/g, (character) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
      }[character]))
      const title = escapeHtml(this.$t('tradingAgents.pdfPreparingTitle'))
      const description = escapeHtml(this.$t('tradingAgents.pdfPreparingDescription'))
      preview.opener = null
      preview.document.title = title
      preview.document.write(`<!doctype html><html lang="${this.isVietnamese ? 'vi' : 'en'}"><head><meta charset="utf-8"><title>${title}</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f7fafc;color:#15324d;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.card{width:min(420px,calc(100vw - 48px));padding:30px;border:1px solid #dbe7f1;border-radius:18px;background:#fff;box-shadow:0 18px 48px rgba(15,48,76,.12)}.spinner{width:26px;height:26px;border:3px solid #dbeafe;border-top-color:#2563eb;border-radius:50%;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}h1{margin:18px 0 8px;font-size:20px}p{margin:0;color:#61758a;line-height:1.55}</style></head><body><main class="card"><div class="spinner" aria-hidden="true"></div><h1>${title}</h1><p>${description}</p></main></body></html>`)
      preview.document.close()
    },
    reportPdfFilename () {
      const symbol = String((this.run && this.run.symbol) || this.targetLabel || 'report').replace(/[\\/:*?"<>|]+/g, '_')
      const date = String((this.run && this.run.analysis_date) || this.analysisDate || this.vietnamToday).replace(/-/g, '')
      return `DataVest_TradingAgents_${symbol}_${date}.pdf`
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
      this.pollGeneration++
      if (this.pollTimer) window.clearInterval(this.pollTimer)
      if (this.progressTimer) window.clearInterval(this.progressTimer)
      this.pollTimer = null
      this.progressTimer = null
    },
    async cancel () {
      if (!this.run || this.cancelling) return
      const runId = this.run.run_id
      const requestId = this.historyRequestId
      this.cancelling = true
      try {
        await cancelTradingAgentsRun(runId)
        if (!this.isCurrentRun(runId, requestId)) return
        this.run = { ...this.run, status: 'cancelled' }
        this.stopPolling()
      } catch (error) {
        if (this.isCurrentRun(runId, requestId)) this.errorMessage = this.$t('tradingAgents.cancelFailed')
      } finally {
        this.cancelling = false
      }
    },
    async resume () {
      if (!this.run || this.resuming) return
      const runId = this.run.run_id
      const requestId = this.historyRequestId
      this.resuming = true
      this.errorMessage = ''
      try {
        await resumeTradingAgentsRun(runId)
        if (!this.isCurrentRun(runId, requestId)) return
        this.run = { ...this.run, status: 'queued' }
        this.startPolling()
      } catch (error) {
        if (this.isCurrentRun(runId, requestId)) this.errorMessage = this.$t('tradingAgents.resumeFailed')
      } finally {
        this.resuming = false
      }
    },
    async clearCheckpoint () {
      if (!this.run || this.clearing) return
      const runId = this.run.run_id
      const requestId = this.historyRequestId
      this.clearing = true
      try {
        await clearTradingAgentsCheckpoint(runId)
        if (!this.isCurrentRun(runId, requestId)) return
        this.$message.success(this.$t('tradingAgents.checkpointCleared'))
      } catch (error) {
        if (this.isCurrentRun(runId, requestId)) this.errorMessage = this.$t('tradingAgents.clearFailed')
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
.report-history-list { display: grid; width: 100%; max-width: 680px; max-height: 320px; gap: 8px; overflow: auto; padding: 2px; text-align: left; }.report-history-item { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 11px 12px; border: 1px solid var(--line, #dbe4ef); border-radius: 9px; background: var(--card, #fff); }.report-history-item div { display: grid; min-width: 0; gap: 2px; }.report-history-item strong { color: var(--ink, #1f2d3d); font-size: 13px; }.report-history-item span { color: var(--muted, #61738b); font-size: 11px; }.report-history-item .ant-btn { flex: 0 0 auto; }.today-run-notice { width: 100%; max-width: 680px; text-align: left; }
.deep-analysis-status-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 8px 0 12px; }.run-state { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; }.run-state--queued, .run-state--running { color: #2563eb; }.run-state--succeeded { color: #16865a; }.run-state--failed, .run-state--cancelled { color: #bd4d4d; }.run-time { color: var(--muted, #61738b); font-size: 12px; }
.deep-analysis-progress { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 10px 16px; padding: 15px; border: 1px solid var(--line, #dbe4ef); border-radius: 10px; background: var(--soft-blue, #f5f9ff); }.deep-analysis-progress .ant-progress { grid-column: 1 / -1; margin: 0; }.progress-copy { display: grid; gap: 3px; min-width: 0; }.progress-copy strong { font-size: 13px; }.progress-copy span { color: var(--muted, #61738b); font-size: 12px; }.progress-copy .progress-current { display: inline-flex; align-items: center; gap: 5px; color: var(--blue, #2563eb); font-weight: 600; }.deep-analysis-stage-list { display: flex; grid-column: 1 / -1; flex-wrap: wrap; gap: 6px; padding-top: 3px; }.deep-analysis-stage { display: inline-flex; align-items: center; gap: 4px; padding: 4px 7px; border: 1px solid var(--line, #dbe4ef); border-radius: 999px; color: var(--muted, #61738b); font-size: 11px; line-height: 1.25; }.deep-analysis-stage.is-complete { border-color: #b7e3cf; color: #16865a; background: #f0fbf5; }.deep-analysis-stage.is-current { border-color: #9fc2ff; color: #245dcc; background: #eef5ff; }.history-recovery-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
.progress-substep { display: flex; align-items: center; gap: 5px; margin-top: 7px !important; color: var(--blue, #245dcc) !important; font-size: 12px !important; font-weight: 600; }.progress-substep .anticon { flex: 0 0 auto; }.deep-analysis-long-running { grid-column: 1 / -1; margin-top: 2px; }
.deep-analysis-recovery { display: grid; gap: 10px; }.recovery-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.deep-analysis-report { margin-top: 14px; overflow: hidden; border: 1px solid var(--line, #dbe4ef); border-radius: 10px; background: var(--card, #fff); }.report-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px 15px; border-bottom: 1px solid var(--line, #dbe4ef); }.report-heading h4 { margin: 0; color: var(--ink, #1f2d3d); font-size: 15px; }.report-heading span { display: block; margin-top: 2px; color: var(--muted, #61738b); font-size: 11px; }.report-heading .ant-tag { margin: 0; }.deep-analysis-report pre { max-height: 52vh; margin: 0; overflow: auto; padding: 16px; color: var(--ink, #1f2d3d); background: transparent; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }.deep-analysis-history-loading, .deep-analysis-report-loading { display: flex; align-items: center; gap: 8px; min-height: 110px; color: var(--muted, #61738b); }.deep-analysis-error { margin-bottom: 12px; }
.deep-analysis-footer { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--line, #dbe4ef); color: var(--muted, #61738b); font-size: 12px; line-height: 1.45; }.deep-analysis-footer span { display: inline-flex; align-items: flex-start; gap: 6px; }
.deep-analysis-report { border-radius: 12px; }.report-heading { align-items: flex-start; padding: 16px 18px; background: var(--soft-blue, #f5f9ff); }.report-heading-copy { min-width: 0; }.report-eyebrow { display: inline-flex !important; align-items: center; gap: 6px; margin: 0 0 5px !important; color: var(--blue, #2563eb) !important; font-size: 11px !important; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }.report-heading h4 { margin: 0; color: var(--ink, #1f2d3d); font-size: 19px; letter-spacing: -.01em; }.report-heading-copy > span:last-child { display: block; margin-top: 5px; color: var(--muted, #61738b); font-size: 12px; line-height: 1.45; }.report-heading-tags { display: flex; flex: 0 0 auto; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }.report-heading .ant-tag { margin: 0; }.report-meta-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; border-bottom: 1px solid var(--line, #dbe4ef); background: var(--line, #dbe4ef); }.report-meta-grid > div { display: grid; gap: 4px; min-width: 0; padding: 10px 14px; background: var(--card, #fff); }.report-meta-grid span { color: var(--muted, #61738b); font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }.report-meta-grid strong { overflow: hidden; color: var(--ink, #1f2d3d); font-size: 12px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }.report-body { max-height: 52vh; overflow: auto; padding: 6px 18px 18px; }.report-block { color: var(--ink, #1f2d3d); }.report-block--heading { margin-top: 14px; }.report-block h5 { margin: 0; color: var(--ink, #1f2d3d); font-size: 13px; line-height: 1.4; }.report-block-title { padding: 10px 0 7px; border-bottom: 1px solid var(--line, #dbe4ef); color: var(--blue, #245dcc) !important; font-size: 15px !important; }.report-block--paragraph p { margin: 8px 0; color: var(--text-secondary, #4f6380); font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }.report-list { display: grid; gap: 7px; margin: 9px 0 12px; padding: 0 0 0 19px; color: var(--text-secondary, #4f6380); font-size: 13px; line-height: 1.6; }.report-list li::marker { color: var(--blue, #2563eb); }.report-empty { padding: 22px 0; color: var(--muted, #61738b); font-size: 13px; }
.report-callout { display: grid; grid-template-columns: minmax(110px, .35fr) minmax(0, .65fr); gap: 12px; align-items: center; margin: 10px 0; padding: 11px 13px; border: 1px solid var(--line, #dbe4ef); border-left: 4px solid var(--blue, #2563eb); border-radius: 9px; background: var(--callout-info-bg, var(--soft-blue, #f5f9ff)); }.report-callout > span { color: var(--muted, #61738b); font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }.report-callout > strong { color: var(--ink, #1f2d3d); font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }.report-callout--positive { border-left-color: #16a34a; background: var(--callout-positive-bg, #f0fdf4); }.report-callout--negative { border-left-color: #dc2626; background: var(--callout-negative-bg, #fff1f2); }.report-callout--hold { border-left-color: #d97706; background: var(--callout-hold-bg, #fffbeb); }.report-callout--positive > strong { color: #166534; }.report-callout--negative > strong { color: #b91c1c; }.report-callout--hold > strong { color: #92400e; }
.theme-dark .report-callout { border-color: #334155; background: #1b2b41; }.theme-dark .report-callout > span { color: #a4b5cc; }.theme-dark .report-callout > strong { color: #e6edf6; }.theme-dark .report-callout--positive { background: #143427; }.theme-dark .report-callout--negative { background: #3b1e27; }.theme-dark .report-callout--hold { background: #3b2c18; }
@media (max-width: 640px) { .report-callout { grid-template-columns: 1fr; gap: 4px; } }
</style>

<style lang="less">
.trading-agents-modal--dark {
  --ink: #e6edf6;
  --muted: #a4b5cc;
  --text-secondary: #b6c3d6;
  --line: #334155;
  --card: #18202c;
  --soft-blue: #152334;
  --blue: #86b7ff;
  .ant-modal-content, .ant-modal-header { background: var(--card); border-color: var(--line); }
  .ant-modal-title, .ant-modal-close, .ant-modal-close-x { color: var(--ink); }
}
@media (max-width: 640px) {
  // Keep a single vertical scroll surface on touch screens. Tables still
  // scroll horizontally inside their own container.
  .trading-agents-modal .report-body { max-height: none !important; overflow: visible; }
  .trading-agents-modal .deep-analysis-report-loading { flex-wrap: wrap; }
}
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
  overflow-wrap: anywhere;
  margin: 0;
  color: var(--ink, #1f2d3d);
  font-size: 14px;
  line-height: 1.35;
  white-space: normal;
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

.trading-agents-modal .report-subsections {
  display: grid;
  gap: 8px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--line, #dbe4ef);
}

.trading-agents-modal .report-subsection {
  overflow: hidden;
  border: 1px solid var(--line, #dbe4ef);
  border-radius: 10px;
  background: var(--card, #fff);
}

.trading-agents-modal .report-subsection-heading {
  appearance: none;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  width: 100%;
  gap: 9px;
  padding: 10px 12px;
  border: 0;
  border-bottom: 1px solid var(--line, #dbe4ef);
  color: inherit;
  background: var(--soft-blue, #f5f9ff);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background .18s ease, box-shadow .18s ease;
}

.trading-agents-modal .report-subsection:not(.is-open) .report-subsection-heading {
  border-bottom: 0;
}

.trading-agents-modal .report-subsection-heading:hover {
  background: #eef5ff;
}

.trading-agents-modal .report-subsection-heading:focus-visible {
  outline: 2px solid var(--blue, #2563eb);
  outline-offset: -2px;
}

.trading-agents-modal .report-subsection-number {
  color: var(--blue, #2563eb);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 10px;
  font-weight: 700;
}

.trading-agents-modal .report-subsection-heading-copy {
  min-width: 0;
}

.trading-agents-modal .report-subsection-heading h6 {
  overflow-wrap: anywhere;
  margin: 0;
  color: var(--ink, #1f2d3d);
  font-size: 13px;
  font-weight: 650;
  line-height: 1.4;
  white-space: normal;
}

.trading-agents-modal .report-subsection-content {
  padding: 10px 12px 12px;
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

.trading-agents-modal .theme-dark .report-subsection {
  background: #18202c;
  border-color: #334155;
}

.trading-agents-modal .theme-dark .report-subsection-heading {
  border-color: #334155;
  background: #1b2b41;
}

.trading-agents-modal .theme-dark .report-subsection-heading h6 {
  color: #e6edf6;
}

.trading-agents-modal .theme-dark .report-subsection-heading:hover {
  background: #20385c;
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

  .trading-agents-modal .report-subsections {
    margin-top: 12px;
    padding-top: 12px;
  }

  .trading-agents-modal .report-subsection-heading {
    padding: 10px;
  }

  .trading-agents-modal .report-block--paragraph p,
  .trading-agents-modal .report-list {
    font-size: 12px;
  }
}
</style>

<style lang="less">
.trading-agents-modal .ant-modal { max-width: calc(100vw - 24px); padding-bottom: 0; }.trading-agents-modal .ant-modal-body { max-height: calc(100dvh - 132px); overflow: auto; padding: 20px 22px; }.trading-agents-modal .theme-dark { color: #e6edf6; }.trading-agents-modal .theme-dark .deep-analysis-context h3, .trading-agents-modal .theme-dark .deep-analysis-empty h4, .trading-agents-modal .theme-dark .report-heading h4, .trading-agents-modal .theme-dark .report-meta-grid strong, .trading-agents-modal .theme-dark .report-block h5 { color: #e6edf6; }.trading-agents-modal .theme-dark .deep-analysis-report { background: #18202c; border-color: #334155; }.trading-agents-modal .theme-dark .deep-analysis-progress { background: #152334; border-color: #334155; }.trading-agents-modal .theme-dark .report-heading { background: #152334; border-color: #334155; }.trading-agents-modal .theme-dark .report-meta-grid { background: #334155; border-color: #334155; }.trading-agents-modal .theme-dark .report-meta-grid > div { background: #18202c; }.trading-agents-modal .theme-dark .report-block--paragraph p, .trading-agents-modal .theme-dark .report-list { color: #b6c3d6; }.trading-agents-modal .theme-dark .report-block-title, .trading-agents-modal .theme-dark .deep-analysis-footer { border-color: #334155; }
 .trading-agents-modal .theme-dark { --callout-info-bg: #1b2b41; --callout-positive-bg: #143427; --callout-negative-bg: #3b1e27; --callout-hold-bg: #3b2c18; }
@media (max-width: 640px) { .trading-agents-modal .ant-modal { top: 12px; margin: 0 auto; }.trading-agents-modal .ant-modal-body { max-height: calc(100dvh - 70px); padding: 16px 14px; }.trading-agents-modal .report-heading { flex-direction: column; gap: 10px; padding: 14px; }.trading-agents-modal .report-heading-tags { justify-content: flex-start; }.trading-agents-modal .report-heading h4 { font-size: 17px; }.trading-agents-modal .report-meta-grid { grid-template-columns: 1fr; }.trading-agents-modal .report-meta-grid > div { padding: 9px 14px; }.trading-agents-modal .report-body { max-height: 48vh; padding: 4px 14px 15px; }.trading-agents-modal .report-block--paragraph p, .trading-agents-modal .report-list { font-size: 12px; } }
</style>
