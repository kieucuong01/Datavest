<template><section><p>{{ $t('portfolioBook.csvHelp') }}</p><textarea v-model="csv" rows="6" :aria-label="$t('portfolioBook.import')" @input="preview = null" /><button :disabled="busy || !csv" @click="inspect">{{ $t('portfolioBook.preview') }}</button><template v-if="preview"><ul v-if="preview.errors.length"><li v-for="(error, i) in preview.errors" :key="i">{{ error.line || '—' }}: {{ error.message }}</li></ul><p v-if="preview.state">{{ preview.events.length }} · {{ $t('portfolioBook.cash') }}: {{ preview.state.cash }} {{ currency }}</p><button :disabled="busy || !preview.valid || preview.revision !== revision" @click="$emit('commit', { csv })">{{ $t('portfolioBook.commit') }}</button></template><p role="alert">{{ error }}</p></section></template>
<script>
import { importPreview } from '@/api/portfolio-books'
export default {
  props: { bookId: { type: String, required: true }, currency: { type: String, required: true }, revision: { type: Number, required: true }, busy: Boolean },
  data () { return { csv: '', preview: null, error: '', requestId: 0 } },
  beforeDestroy () { this.requestId++ },
  methods: { async inspect () { const ticket = ++this.requestId; const csv = this.csv; this.error = ''; try { const result = await importPreview(this.bookId, { csv }); if (ticket === this.requestId && csv === this.csv) this.preview = result.data } catch (e) { if (ticket === this.requestId) this.error = e.response?.data?.message || this.$t('portfolioBook.error') } } }
}
</script>
<style scoped>textarea{width:100%;background:transparent;color:inherit;border:1px solid #8290a5;border-radius:6px;padding:10px}button{margin:10px 10px 0 0;padding:8px 12px}p[role=alert]{color:#dc2626}</style>
