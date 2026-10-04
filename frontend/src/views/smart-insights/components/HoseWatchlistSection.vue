<template>
  <section class="hose-pilot" aria-labelledby="hose-pilot-title">
    <header><div><h2 id="hose-pilot-title">{{ vi ? 'Nghiên cứu HOSE · thí điểm' : 'HOSE research · pilot' }}</h2><p>{{ vi ? 'Ba ngành đại diện, theo dõi qua watchlist. Đây là phạm vi thử nghiệm, không phải danh sách khuyến nghị mua.' : 'Three representative sectors, followed through your watchlist. This pilot is not a buy list.' }}</p></div><button type="button" :disabled="loading" @click="load">{{ vi ? 'Làm mới' : 'Refresh' }}</button></header>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="loading" aria-live="polite">{{ vi ? 'Đang tải danh sách…' : 'Loading assets…' }}</p>
    <div v-else class="hose-pilot-grid">
      <article v-for="asset in rows" :key="asset.symbol">
        <div><strong>{{ asset.symbol }}</strong><span v-if="asset.following">★ {{ vi ? 'Đang theo dõi' : 'Following' }}</span></div>
        <p>{{ asset.name }} · {{ asset.selectionReason }}</p>
        <small>{{ vi ? 'Giá theo ngày · VND · nguồn và khoảng trống trong báo cáo' : 'Daily prices · VND · sources and gaps in the report' }}</small>
        <button type="button" :disabled="adding === asset.symbol" @click="followOrOpen(asset)">{{ asset.following ? (vi ? 'Xem nghiên cứu' : 'Open research') : (vi ? 'Thêm watchlist' : 'Add to watchlist') }}</button>
      </article>
    </div>
    <small class="hose-context">{{ vi ? 'VNINDEX / VN30 là chỉ số tham chiếu, không phải cổ phiếu. Bằng chứng chỉ xuất hiện khi báo cáo đã thu thập được dữ liệu; thiếu dữ liệu không có nghĩa là doanh nghiệp không có rủi ro.' : 'VNINDEX / VN30 are reference indices, not equities. Evidence appears only after a report captures it; missing data does not mean a company has no risk.' }}</small>
  </section>
</template>

<script>
import { getHoseResearchPilot } from '@/api/smart-insights'
import { addWatchlist, getWatchlist } from '@/api/market'
import { hosePilotRows } from '@/utils/hoseResearch'

export default {
  name: 'HoseWatchlistSection',
  props: { guest: { type: Boolean, default: true } },
  data: () => ({ assets: [], watchlist: [], loading: false, adding: '', error: '', generation: 0 }),
  computed: {
    vi () { return this.$i18n.locale === 'vi-VN' },
    rows () { return hosePilotRows(this.assets, this.watchlist) }
  },
  watch: { guest () { this.watchlist = []; this.load() } },
  mounted () { this.load() },
  beforeDestroy () { this.generation++ },
  methods: {
    async load () {
      const generation = ++this.generation
      this.loading = true
      this.error = ''
      try {
        const [pilot, watchlist] = await Promise.all([getHoseResearchPilot(), this.guest ? Promise.resolve(null) : getWatchlist()])
        if (generation !== this.generation) return
        if (!pilot || pilot.code !== 1) throw new Error('pilot unavailable')
        this.assets = (pilot.data && pilot.data.assets) || []
        if (watchlist && watchlist.code !== 1) throw new Error('watchlist unavailable')
        this.watchlist = watchlist && Array.isArray(watchlist.data) ? watchlist.data : []
      } catch (_) {
        if (generation === this.generation) this.error = this.vi ? 'Chưa tải được dữ liệu. Vui lòng thử lại.' : 'Data could not be loaded. Please retry.'
      } finally { if (generation === this.generation) this.loading = false }
    },
    async followOrOpen (asset) {
      if (this.guest) { this.$emit('sign-in', asset); return }
      if (asset.following) { this.$emit('open-research', asset); return }
      const generation = this.generation
      this.adding = asset.symbol
      this.error = ''
      try {
        const response = await addWatchlist({ market: 'VNStock', symbol: asset.symbol, name: asset.name })
        if (generation !== this.generation || this.guest) return
        if (!response || response.code !== 1) throw new Error('watchlist failed')
        await this.load()
        this.$emit('watchlist-changed')
      } catch (_) {
        if (generation === this.generation) this.error = this.vi ? 'Chưa thêm được mã vào watchlist. Vui lòng thử lại.' : 'Could not add this asset. Please retry.'
      } finally { this.adding = '' }
    }
  }
}
</script>

<style scoped>
.hose-pilot { margin: 18px 0; padding: 20px; background: var(--card, #fff); color: var(--ink, #23334b); border: 1px solid var(--line, #dce4ee); border-radius: 14px; }
header { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; } h2 { margin:0; color:inherit; font-size:18px; } p { margin:7px 0; font-size:13px; line-height:1.5; } small { color: var(--muted, #60708a); line-height:1.5; }
.hose-pilot-grid { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; margin:16px 0; } article { padding:14px; background:var(--soft-blue, #f5f8fd); border:1px solid var(--line, #dce4ee); border-radius:10px; } article div { display:flex; align-items:center; gap:12px; } article strong { font-size:20px; } article span { font-size:11px; color:var(--blue, #176bcb); } article button { display:block; margin-top:12px; }
button { border:1px solid var(--line, #cbd7e6); border-radius:7px; background:var(--card, white); color:var(--blue, #176bcb); padding:7px 12px; cursor:pointer; } button:focus-visible { outline:2px solid #176bcb; outline-offset:3px; } button:disabled { opacity:.6; cursor:wait; }
@media (max-width:680px) { .hose-pilot-grid { grid-template-columns:1fr; } .hose-pilot { padding:14px; } }
</style>
