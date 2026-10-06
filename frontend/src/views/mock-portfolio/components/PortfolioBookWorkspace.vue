<template>
  <section class="book-workspace">
    <p>{{ $t('portfolioBook.boundary') }}</p>
    <div class="book-toolbar"><select v-model="selectedId" :aria-label="$t('portfolioBook.select')" @change="loadBook"><option value="">{{ $t('portfolioBook.select') }}</option><option v-for="item in books" :key="item.id" :value="item.id">{{ item.name }} · {{ item.currency }}</option></select><input v-model="newName" :placeholder="$t('portfolioBook.name')" maxlength="100"><select v-model="newCurrency" :aria-label="$t('portfolioBook.currency')"><option>VND</option><option>USD</option><option>USDT</option></select><button :disabled="busy || !newName.trim()" @click="create">{{ $t('portfolioBook.create') }}</button></div>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!book">{{ $t('portfolioBook.empty') }}</p>
    <template v-else>
      <div class="book-metrics"><div v-for="metric in metrics" :key="metric.key"><span>{{ $t('portfolioBook.' + metric.label) }}</span><strong>{{ book.state[metric.key] }} {{ book.currency }}</strong></div></div>
      <p>{{ $t('portfolioBook.revision') }} {{ book.revision }}</p>
      <h2>{{ $t('portfolioBook.positions') }}</h2><div class="table-scroll"><table><thead><tr><th>{{ $t('portfolioBook.symbol') }}</th><th>{{ $t('portfolioBook.quantity') }}</th><th>{{ $t('portfolioBook.unitPrice') }}</th></tr></thead><tbody><tr v-for="position in book.state.positions" :key="position.market + position.symbol"><td>{{ position.symbol }}</td><td>{{ position.quantity }}</td><td>{{ position.averageCost }} {{ book.currency }}</td></tr></tbody></table></div>
      <details v-if="book.revision === 0 && openingCandidates.length"><summary>{{ $t('portfolioBook.opening') }}</summary><p>{{ $t('portfolioBook.openingHelp') }}</p><label v-for="position in openingCandidates" :key="position.id"><input v-model="openingIds" type="checkbox" :value="position.id">{{ position.symbol }} · {{ position.quantity }}</label><label>{{ $t('portfolioBook.openingCash') }}<input v-model="openingCash" inputmode="decimal" @input="opening = null"></label><input v-model="openingTime" type="datetime-local" @input="opening = null"><button :disabled="busy || !openingIds.length" @click="previewOpening">{{ $t('portfolioBook.preview') }}</button><p v-if="opening">{{ $t('portfolioBook.cash') }}: {{ opening.state.cash }} · {{ opening.events.length }}</p><button v-if="opening" :disabled="busy" @click="commitOpening">{{ $t('portfolioBook.commit') }}</button></details>
      <h2>{{ $t('portfolioBook.entries') }}</h2>
      <LedgerEntryForm :key="selectedId + ':' + (editing?.eventId || book.revision)" :currency="book.currency" :entry="editing" :busy="busy" @save="saveEntry" />
      <button v-if="editing" @click="editing = null">{{ $t('common.cancel') }}</button>
      <div class="table-scroll"><table><thead><tr><th>{{ $t('portfolioBook.effectiveAt') }}</th><th>{{ $t('portfolioBook.type') }}</th><th>{{ $t('portfolioBook.symbol') }}</th><th>{{ $t('portfolioBook.amount') }}</th><th></th></tr></thead><tbody><tr v-for="entry in entries" :key="entry.eventId" :class="{ cancelled: entry.cancelled }"><td>{{ localTime(entry.effectiveAt) }}</td><td>{{ $t('portfolioBook.' + entry.type) }}</td><td>{{ entry.symbol }}</td><td>{{ entry.quantity !== '0' ? entry.quantity + ' × ' + entry.unitPrice : entry.amount }}</td><td><button :disabled="busy || entry.cancelled" @click="editing = entry">{{ $t('portfolioBook.edit') }}</button><button :disabled="busy || entry.cancelled" @click="cancelEntry(entry)">{{ $t('portfolioBook.cancel') }}</button><button @click="showAudit(entry)">{{ $t('portfolioBook.audit') }}</button></td></tr></tbody></table></div>
      <a-pagination v-if="total > 50" :current="page" :total="total" :page-size="50" @change="changePage" />
      <pre v-if="audit">{{ audit }}</pre>
      <details><summary>{{ $t('portfolioBook.import') }}</summary><LedgerImport
        :key="selectedId + book.revision"
        :book-id="selectedId"
        :currency="book.currency"
        :revision="book.revision"
        :busy="busy"
        @commit="commitCsv" /></details>
    </template>
  </section>
</template>
<script>
import * as bookApi from '@/api/portfolio-books'
import LedgerEntryForm from './LedgerEntryForm.vue'
import LedgerImport from './LedgerImport.vue'
export default {
  components: { LedgerEntryForm, LedgerImport },
  props: { legacyPositions: { type: Array, default: () => [] } },
  data () { return { books: [], selectedId: '', book: null, entries: [], total: 0, page: 1, newName: '', newCurrency: 'VND', busy: false, error: '', editing: null, audit: null, ticket: 0, openingIds: [], openingCash: '0', openingTime: new Date(Date.now() + 7 * 3600000).toISOString().slice(0, 16), opening: null, requestKey: null, pendingPayload: null, metrics: [{ key: 'cash', label: 'cash' }, { key: 'realizedPnl', label: 'realized' }, { key: 'income', label: 'income' }] } },
  computed: { openingCandidates () { return this.legacyPositions.filter(p => p.side === 'long' && (p.quote_currency || (p.market === 'VNStock' ? 'VND' : p.market === 'Forex' ? 'USD' : p.symbol.split('/')[1])) === this.book?.currency) } },
  mounted () { this.loadBooks() },
  beforeDestroy () { this.ticket++ },
  watch: { openingIds () { this.opening = null } },
  methods: {
    localTime (value) { return new Date(value).toLocaleString(this.$i18n.locale, { timeZone: 'Asia/Ho_Chi_Minh' }) },
    async loadBooks () { try { const result = await bookApi.listBooks(); this.books = result.data || [] } catch (e) { this.error = this.$t('portfolioBook.error') } },
    async loadBook () {
      const ticket = ++this.ticket; const id = this.selectedId; this.book = null; this.entries = []; this.editing = null; this.audit = null; this.opening = null; this.openingIds = []; this.error = ''; this.page = 1
      if (!id) return
      try { const [state, entries] = await Promise.all([bookApi.bookState(id), bookApi.bookEntries(id)]); if (ticket !== this.ticket || id !== this.selectedId) return; this.book = state.data; this.entries = entries.data.entries; this.total = entries.data.total } catch (e) { if (ticket === this.ticket) this.error = e.response?.data?.message || this.$t('portfolioBook.error') }
    },
    async create () { this.busy = true; try { const result = await bookApi.createBook({ name: this.newName, currency: this.newCurrency }); await this.loadBooks(); this.selectedId = result.data.id; this.newName = ''; await this.loadBook() } catch (e) { this.error = e.response?.data?.message || this.$t('portfolioBook.error') } finally { this.busy = false } },
    async mutate (method, payload, eventId) {
      const id = this.selectedId; const revision = this.book.revision
      const signature = JSON.stringify({ id, method, payload, eventId, revision })
      if (this.pendingPayload !== signature) { this.pendingPayload = signature; this.requestKey = crypto.randomUUID() }
      this.busy = true; this.error = ''
      try { const data = { ...payload, expectedRevision: revision, requestKey: this.requestKey }; await (eventId ? bookApi[method](id, eventId, data) : bookApi[method](id, data)); this.pendingPayload = null; this.requestKey = null; if (id === this.selectedId) await this.loadBook() } catch (e) { this.error = e.response?.data?.message || this.$t('portfolioBook.error'); if (e.response?.status === 409) { this.pendingPayload = null; await this.loadBook(); this.error = this.$t('portfolioBook.stale') } } finally { this.busy = false }
    },
    saveEntry (event) { return this.editing ? this.mutate('reviseEntry', { event }, this.editing.eventId) : this.mutate('addEntries', { events: [event] }) },
    cancelEntry (entry) { this.$confirm({ title: this.$t('portfolioBook.confirmCancel'), onOk: () => this.mutate('reviseEntry', { cancelled: true }, entry.eventId) }) },
    commitCsv (payload) { return this.mutate('importCommit', payload) },
    async changePage (page) { const ticket = ++this.ticket; const id = this.selectedId; try { const result = await bookApi.bookEntries(id, { offset: (page - 1) * 50 }); if (ticket === this.ticket && id === this.selectedId) { this.entries = result.data.entries; this.page = page } } catch (e) { if (ticket === this.ticket) this.error = this.$t('portfolioBook.error') } },
    async showAudit (entry) { const id = this.selectedId; const ticket = this.ticket; try { const result = await bookApi.entryRevisions(id, entry.eventId); if (id === this.selectedId && ticket === this.ticket) this.audit = JSON.stringify(result.data, null, 2) } catch (e) { this.error = this.$t('portfolioBook.error') } },
    openingPayload () { return { positionIds: this.openingIds, cash: this.openingCash, effectiveAt: new Date(this.openingTime + ':00+07:00').toISOString() } },
    async previewOpening () { const id = this.selectedId; const ticket = this.ticket; try { const result = await bookApi.openingPreview(id, this.openingPayload()); if (id === this.selectedId && ticket === this.ticket) this.opening = result.data } catch (e) { this.error = e.response?.data?.message || this.$t('portfolioBook.error') } },
    commitOpening () { return this.mutate('openingCommit', { ...this.openingPayload(), fingerprint: this.opening.fingerprint }) }
  }
}
</script>
<style scoped>
.book-workspace{padding:20px;background:var(--card-bg,transparent);border:1px solid #8290a540;border-radius:14px}.book-toolbar{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}select,input,button{padding:8px;border:1px solid #8290a5;border-radius:6px;background:transparent;color:inherit}button{cursor:pointer}button:disabled{opacity:.5}.book-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:24px 0}.book-metrics div{display:grid;gap:8px}.book-metrics strong{font-size:21px}.table-scroll{overflow:auto;margin:20px 0}table{width:100%;min-width:640px}th,td{text-align:left;padding:12px;border-bottom:1px solid #8290a540}td button{margin:3px}.cancelled{text-decoration:line-through;opacity:.5}details{margin:20px 0;padding:14px;border:1px solid #8290a540;border-radius:8px}summary{cursor:pointer}pre{max-height:300px;overflow:auto}p[role=alert]{color:#dc2626}@media(max-width:600px){.book-workspace{padding:12px}.book-metrics{grid-template-columns:1fr}}
</style>
