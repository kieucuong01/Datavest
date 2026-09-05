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
          <a-progress :percent="progressPercent" :show-info="false" status="active" />
          <div class="progress-copy">
            <strong>{{ $t('tradingAgents.runningTitle') }}</strong>
            <span>{{ $t('tradingAgents.progressPercent', { percent: progressPercent }) }} · {{ $t('tradingAgents.completedStages', { completed: progressSnapshot.completed_count || 0, total: progressTotal }) }}</span>
            <span class="progress-current"><a-icon type="loading" /> {{ $t('tradingAgents.currentStage') }}: {{ currentStageLabel }}</span>
          </div>
          <a-button size="small" :loading="cancelling" @click="cancel">
            <a-icon type="stop" /> {{ $t('tradingAgents.cancel') }}
          </a-button>
          <div class="deep-analysis-stage-list" role="list" :aria-label="$t('tradingAgents.currentStage')">
            <span v-for="stage in progressStages" :key="stage.id" class="deep-analysis-stage" :class="{ 'is-complete': stage.complete, 'is-current': stage.current }" role="listitem">
              <a-icon :type="stage.complete ? 'check-circle' : (stage.current ? 'loading' : 'clock-circle')" />
              {{ stage.label }}
            </span>
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
            <div><h4 id="deep-analysis-report-title">{{ $t('tradingAgents.reportTitle') }}</h4><span>{{ $t('tradingAgents.reportProvenance') }}</span></div>
            <a-tag color="green"><a-icon type="safety-certificate" /> {{ $t('tradingAgents.researchOnly') }}</a-tag>
          </div>
          <pre v-text="reportContent" />
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
      historyLoading: false,
      historyRequestId: 0,
      historyError: ''
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
        total_count: this.progressStageIds.length
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
      this.refreshRun()
      this.pollTimer = window.setInterval(() => this.refreshRun(), 2500)
    },
    restorePolling () {
      if (this.isRunning) this.startPolling()
      else if (this.run && String(this.run.status || '').toLowerCase() === 'succeeded') this.loadReport(this.run)
    },
    stopPolling () {
      if (this.pollTimer) window.clearInterval(this.pollTimer)
      this.pollTimer = null
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
@media (max-width: 640px) { .deep-analysis-context { flex-direction: column; gap: 10px; }.deep-analysis-context h3 { font-size: 18px; }.deep-analysis-provenance { justify-content: flex-start; }.deep-analysis-empty { min-height: 230px; padding: 28px 12px; }.deep-analysis-status-row { align-items: flex-start; flex-direction: column; }.deep-analysis-progress { grid-template-columns: 1fr; }.deep-analysis-progress .ant-btn { width: 100%; min-height: 44px; }.deep-analysis-stage-list { display: grid; grid-template-columns: 1fr; }.deep-analysis-stage { min-height: 32px; }.history-recovery-actions { display: grid; grid-template-columns: 1fr; width: 100%; }.history-recovery-actions .ant-btn { min-height: 44px; }.recovery-actions { display: grid; grid-template-columns: 1fr; }.recovery-actions .ant-btn { min-height: 44px; }.report-heading { align-items: flex-start; flex-direction: column; }.deep-analysis-report pre { max-height: 48vh; padding: 13px; font-size: 11px; }.deep-analysis-footer { align-items: stretch; flex-direction: column; }.deep-analysis-footer .ant-btn { min-height: 44px; } }
</style>

<style lang="less">
.trading-agents-modal .ant-modal { max-width: calc(100vw - 24px); padding-bottom: 0; }.trading-agents-modal .ant-modal-body { max-height: calc(100dvh - 132px); overflow: auto; padding: 20px 22px; }.trading-agents-modal .theme-dark { color: #e6edf6; }.trading-agents-modal .theme-dark .deep-analysis-context h3, .trading-agents-modal .theme-dark .deep-analysis-empty h4, .trading-agents-modal .theme-dark .report-heading h4, .trading-agents-modal .theme-dark .deep-analysis-report pre { color: #e6edf6; }.trading-agents-modal .theme-dark .deep-analysis-report { background: #18202c; border-color: #334155; }.trading-agents-modal .theme-dark .deep-analysis-progress { background: #152334; border-color: #334155; }.trading-agents-modal .theme-dark .report-heading, .trading-agents-modal .theme-dark .deep-analysis-footer { border-color: #334155; }
@media (max-width: 640px) { .trading-agents-modal .ant-modal { top: 12px; margin: 0 auto; }.trading-agents-modal .ant-modal-body { max-height: calc(100dvh - 70px); padding: 16px 14px; } }
</style>
