<template>
  <form class="ledger-form" @submit.prevent="submit">
    <label>{{ $t('portfolioBook.type') }}<select v-model="form.type"><option v-for="kind in types" :key="kind" :value="kind">{{ $t('portfolioBook.' + kind) }}</option></select></label>
    <label>{{ $t('portfolioBook.effectiveAt') }}<input v-model="form.localTime" type="datetime-local" required></label>
    <template v-if="isAsset">
      <label>{{ $t('portfolioBook.market') }}<select v-model="form.market"><option v-for="market in markets" :key="market">{{ market }}</option></select></label>
      <label>{{ $t('portfolioBook.symbol') }}<input v-model="form.symbol" required maxlength="40" :placeholder="currency === 'VND' ? 'FPT' : currency === 'USD' ? 'XAUUSD' : 'BTC/USDT'"></label>
      <label>{{ $t('portfolioBook.quantity') }}<input v-model="form.quantity" inputmode="decimal" required></label>
      <label v-if="form.type !== 'split'">{{ $t('portfolioBook.unitPrice') }}<input v-model="form.unitPrice" inputmode="decimal" required></label>
    </template>
    <label v-else>{{ $t('portfolioBook.amount') }} ({{ currency }})<input v-model="form.amount" inputmode="decimal" required></label>
    <template v-if="form.type === 'buy' || form.type === 'sell'"><label>{{ $t('portfolioBook.fee') }}<input v-model="form.fee" inputmode="decimal"></label><label>{{ $t('portfolioBook.tax') }}<input v-model="form.tax" inputmode="decimal"></label></template>
    <label class="wide">{{ $t('portfolioBook.notes') }}<input v-model="form.notes" maxlength="2000"></label>
    <button type="submit" :disabled="busy">{{ $t('portfolioBook.save') }}</button>
  </form>
</template>
<script>
const vnLocalTime = iso => new Date(new Date(iso || Date.now()).getTime() + 7 * 3600000).toISOString().slice(0, 16)
export default {
  props: { currency: { type: String, required: true }, entry: { type: Object, default: null }, busy: Boolean },
  data () { return { form: {} } },
  computed: {
    types () { return this.entry?.type === 'opening_position' ? ['opening_position'] : ['deposit', 'withdraw', 'buy', 'sell', 'dividend', 'fee', 'tax', 'split'] },
    markets () { return this.currency === 'VND' ? ['VNStock'] : this.currency === 'USD' ? ['Forex'] : ['Crypto'] },
    isAsset () { return ['buy', 'sell', 'split', 'opening_position'].includes(this.form.type) }
  },
  watch: { entry: { immediate: true, handler (entry) { this.form = { type: 'deposit', market: this.currency === 'VND' ? 'VNStock' : this.currency === 'USD' ? 'Forex' : 'Crypto', symbol: '', quantity: '', unitPrice: '', amount: '', fee: '0', tax: '0', notes: '', ...entry, localTime: vnLocalTime(entry?.effectiveAt) } } } },
  methods: {
    submit () {
      const { localTime, ...form } = this.form
      const payload = { type: form.type, effectiveAt: new Date(localTime + ':00+07:00').toISOString(), notes: form.notes }
      if (this.isAsset) Object.assign(payload, { market: form.market, symbol: form.symbol, quantity: form.quantity, unitPrice: form.type === 'split' ? '0' : form.unitPrice })
      else payload.amount = form.amount
      if (['buy', 'sell'].includes(form.type)) Object.assign(payload, { fee: form.fee, tax: form.tax })
      this.$emit('save', payload)
    }
  }
}
</script>
<style scoped>
.ledger-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}label{display:grid;gap:5px}input,select{width:100%;border:1px solid #8290a5;border-radius:6px;padding:9px;background:transparent;color:inherit}.wide{grid-column:1/-1}button{padding:10px;border:0;border-radius:6px;background:#2563eb;color:white}button:disabled{opacity:.5}@media(max-width:600px){.ledger-form{grid-template-columns:1fr}}
</style>
