<template>
  <section class="alert-preferences"><h2>{{ $t('portfolioBook.alertTitle') }}</h2><p>{{ $t('portfolioBook.alertDisclosure') }}</p><form @submit.prevent="save">
    <label><input v-model="form.enabled" type="checkbox">{{ $t('portfolioBook.enableAlerts') }}</label>
    <div class="preferences-grid"><label>{{ $t('portfolioBook.threshold') }}<input v-model.number="form.concentrationPct" type="number" min="1" max="100" required></label><label>{{ $t('portfolioBook.digestHours') }}<input v-model.number="form.digestHours" type="number" min="6" max="168" required></label><label>{{ $t('portfolioBook.cooldownHours') }}<input v-model.number="form.cooldownHours" type="number" min="6" max="168" required></label></div>
    <label><input v-model="form.dataQuality" type="checkbox">{{ $t('portfolioBook.dataAlerts') }}</label><label><input v-model="form.reports" type="checkbox">{{ $t('portfolioBook.reportAlerts') }}</label><label><input v-model="form.events" type="checkbox">{{ $t('portfolioBook.eventAlerts') }}</label>
    <button :disabled="loading || saving" type="submit">{{ $t('portfolioBook.savePreferences') }}</button><span v-if="saved" role="status">{{ $t('portfolioBook.preferencesSaved') }}</span></form>
    <p v-if="form.enabled && form.nextDigestAt">{{ $t('portfolioBook.nextDigest') }}: {{ localTime(form.nextDigestAt) }}</p><p v-if="error" role="alert">{{ error }}</p>
    <details><summary>{{ $t('portfolioBook.inAppNotifications') }}</summary><button :disabled="loading" @click="loadNotifications">{{ $t('portfolioBook.loadNotifications') }}</button><p v-if="!notifications.length">{{ $t('portfolioBook.noNotifications') }}</p><article v-for="notice in notifications" :key="notice.id"><strong>{{ notice.title }}</strong><p class="message">{{ notice.message }}</p><div v-for="(item,index) in payloadItems(notice)" :key="index"><a v-if="externalSource(item.evidence?.sourceUrl)" :href="item.evidence.sourceUrl" target="_blank" rel="noopener noreferrer">{{ item.assetKey }} · {{ $t('portfolioBook.source') }}</a><span v-else-if="item.rule === 'report_change'">{{ item.assetKey }} · {{ (item.evidence.fields || []).join(', ') }}<button @click="selectedReport = item">{{ $t('portfolioBook.source') }}</button></span></div><button v-if="!notice.is_read" @click="markRead(notice)">{{ $t('portfolioBook.markRead') }}</button></article><ReportPdfReader v-if="selectedReport" :shared-asset-key="selectedReport.assetKey" :effective-date="selectedReport.evidence.effectiveDate" variant="summary" /></details>
  </section>
</template>
<script>
import { getAlertPreferences, saveAlertPreferences, markBookNotificationRead } from '@/api/portfolio-books'
import { getStrategyNotifications } from '@/api/strategy'
import ReportPdfReader from '@/components/TradingAgents/ReportPdfReader.vue'
export default {
  components: { ReportPdfReader },
  props: { bookId: { type: String, required: true } },
  data () { return { form: { enabled: false, concentrationPct: 50, dataQuality: true, reports: true, events: false, digestHours: 24, cooldownHours: 6 }, loading: false, saving: false, saved: false, error: '', ticket: 0, notifications: [], selectedReport: null } },
  watch: { bookId () { this.notifications = []; this.selectedReport = null; this.load() } },
  mounted () { this.load() },
  beforeDestroy () { this.ticket++ },
  methods: {
    localTime (value) { return new Date(value).toLocaleString(this.$i18n.locale, { timeZone: 'Asia/Ho_Chi_Minh' }) },
    payloadItems (notice) { try { const payload = typeof notice.payload_json === 'string' ? JSON.parse(notice.payload_json) : notice.payload_json; return (payload?.items || []).filter(item => item.bookId === this.bookId) } catch (e) { return [] } },
    externalSource (url) { try { const parsed = new URL(url); return ['https:', 'http:'].includes(parsed.protocol) && !parsed.username } catch (e) { return false } },
    async load () { const ticket = ++this.ticket; const id = this.bookId; this.loading = true; this.error = ''; try { const result = await getAlertPreferences(id); if (ticket === this.ticket && id === this.bookId) this.form = result.data } catch (e) { if (ticket === this.ticket) this.error = this.$t('portfolioBook.error') } finally { if (ticket === this.ticket) this.loading = false } },
    async save () { const ticket = ++this.ticket; const id = this.bookId; this.saving = true; this.saved = false; this.error = ''; try { const result = await saveAlertPreferences(id, this.form); if (ticket === this.ticket && id === this.bookId) { this.form = result.data; this.saved = true } } catch (e) { if (ticket === this.ticket) this.error = e.response?.data?.message || this.$t('portfolioBook.error') } finally { if (ticket === this.ticket) this.saving = false } },
    async loadNotifications () { const id = this.bookId; const ticket = this.ticket; try { const result = await getStrategyNotifications({ limit: 200 }); if (id === this.bookId && ticket === this.ticket) this.notifications = (result.data.items || []).filter(notice => notice.signal_type === 'portfolio_digest' && this.payloadItems(notice).length) } catch (e) { this.error = this.$t('portfolioBook.error') } },
    async markRead (notice) { try { await markBookNotificationRead({ id: notice.id }); notice.is_read = 1 } catch (e) { this.error = this.$t('portfolioBook.error') } }
  }
}
</script>
<style scoped>.alert-preferences{margin:24px 0;padding:20px;border:1px solid #8290a540;border-radius:12px}label{display:block;margin:10px 0}.preferences-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.preferences-grid input{display:block;width:100%;padding:8px;border:1px solid #8290a5;background:transparent;color:inherit}button{margin:10px 12px 10px 0;padding:8px 12px;background:transparent;color:inherit;border:1px solid #8290a5;border-radius:6px}.message{white-space:pre-wrap}article{padding:16px 0;border-bottom:1px solid #8290a540}p[role=alert]{color:#dc2626}@media(max-width:600px){.preferences-grid{grid-template-columns:1fr}}</style>
