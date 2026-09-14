<template>
  <section class="report-pdf-reader" :aria-busy="loading">
    <div class="pdf-toolbar">
      <span>{{ $t('tradingAgents.pdfReaderHint') }}</span>
      <a-button :disabled="!pdfUrl" @click="openFullSize">
        <a-icon type="export" /> {{ $t('tradingAgents.pdfOpenTab') }}
      </a-button>
    </div>
    <div v-if="loading" class="pdf-status" role="status">
      <a-spin /> <span>{{ $t('tradingAgents.pdfPreparingTitle') }}</span>
    </div>
    <div v-else-if="error" class="pdf-status" role="alert">
      <span>{{ $t('tradingAgents.pdfExportFailed') }}</span>
      <a-button @click="loadPdf">{{ $t('tradingAgents.retryReport') }}</a-button>
    </div>
    <iframe v-else-if="pdfUrl" :src="pdfUrl + '#view=FitH&navpanes=0'" :title="$t('tradingAgents.reportTitle')" class="pdf-frame" />
  </section>
</template>

<script>
import { getTradingAgentsReportPdf, getTradingAgentsSummaryPdf } from '@/api/trading-agents'
import { getPublicResearchReportPdf, getPublicResearchReportSummaryPdf, getSharedResearchReportPdf } from '@/api/smart-insights'

export default {
  name: 'ReportPdfReader',
  props: {
    runId: { type: String, default: '' },
    publicAssetKey: { type: String, default: '' },
    sharedAssetKey: { type: String, default: '' },
    variant: { type: String, default: 'full' },
    pdfRevision: { type: [Number, String], default: 0 },
    active: { type: Boolean, default: true }
  },
  data: () => ({ pdfUrl: '', pdfBlob: null, loading: false, error: false, generation: 0 }),
  watch: {
    pdfSource: { immediate: true, handler () { this.reset(); if (this.active) this.loadPdf() } },
    active (value) { if (value) { this.reset(); this.loadPdf() } else this.reset() }
  },
  computed: {
    pdfSource () { return `${this.sharedAssetKey || this.publicAssetKey || this.runId}:${this.variant}:${this.pdfRevision}` }
  },
  beforeDestroy () { this.reset() },
  methods: {
    reset () {
      this.generation++
      if (this.pdfUrl) URL.revokeObjectURL(this.pdfUrl)
      this.pdfUrl = ''
      this.pdfBlob = null
      this.loading = false
      this.error = false
    },
    async loadPdf () {
      if ((!this.runId && !this.publicAssetKey && !this.sharedAssetKey) || !this.active || this.loading || this.pdfUrl) return
      const generation = ++this.generation
      const revision = this.pdfRevision || Date.now()
      this.loading = true
      this.error = false
      try {
        const response = this.sharedAssetKey
          ? await getSharedResearchReportPdf(this.sharedAssetKey, revision, this.variant)
          : this.publicAssetKey
          ? this.variant === 'summary'
            ? await getPublicResearchReportSummaryPdf(this.publicAssetKey, revision)
            : await getPublicResearchReportPdf(this.publicAssetKey, revision)
          : this.variant === 'summary'
            ? await getTradingAgentsSummaryPdf(this.runId, revision)
            : await getTradingAgentsReportPdf(this.runId, revision)
        if (generation !== this.generation) return
        const blob = response instanceof Blob ? response : response.data
        if (!(blob instanceof Blob) || !blob.size) throw new Error('Empty PDF')
        this.pdfBlob = new Blob([blob], { type: 'application/pdf' })
        this.pdfUrl = URL.createObjectURL(this.pdfBlob)
      } catch (_) {
        if (generation === this.generation) this.error = true
      } finally {
        if (generation === this.generation) this.loading = false
      }
    },
    openFullSize () {
      if (!this.pdfBlob) return
      // Independent URL keeps the new tab readable after the modal closes.
      const url = URL.createObjectURL(this.pdfBlob)
      window.open(url, '_blank', 'noopener,noreferrer')
      window.setTimeout(() => URL.revokeObjectURL(url), 300000)
    }
  }
}
</script>

<style scoped>
.report-pdf-reader { min-width: 0; width: 100%; }
.pdf-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 12px 0; }
.pdf-toolbar span { font-size: 12px; flex: 1 1 220px; }
.pdf-toolbar button { min-height: 40px; }
.pdf-frame { display: block; width: 100%; height: 78vh; min-height: 520px; border: 1px solid #d8e1ee; border-radius: 8px; background: #f1f5f9; }
.pdf-status { min-height: 240px; display: flex; align-items: center; justify-content: center; gap: 16px; flex-direction: column; padding: 24px; text-align: center; }
@media (max-width: 600px) { .pdf-frame { height: 65vh; min-height: 320px; } .pdf-toolbar button { width: 100%; min-height: 44px; } }
</style>
