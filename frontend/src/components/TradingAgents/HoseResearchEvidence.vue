<template>
  <section v-if="evidence" class="hose-research" aria-labelledby="hose-evidence-title">
    <h3 id="hose-evidence-title">{{ evidence.symbol }} · {{ vi ? 'Bằng chứng HOSE của báo cáo' : 'Report HOSE evidence' }}</h3>
    <p>{{ evidence.name }} <span v-if="evidence.sector">· {{ evidence.sector }}</span> · {{ evidence.asOf }}</p>
    <div class="hose-price"><strong>{{ number(evidence.price.value, 'VND') }}</strong><span>{{ evidence.price.status }} · {{ evidence.price.source }} · {{ evidence.price.tradeDate || '—' }}</span><small>{{ vi ? 'Tải lúc' : 'Retrieved' }}: {{ evidence.price.retrievedAt || '—' }} · {{ evidence.price.priceMode }} · {{ vi ? 'Khối lượng' : 'Volume' }}: {{ number(evidence.price.volume) }}</small></div>
    <div class="hose-benchmarks"><span v-for="row in evidence.benchmarks" :key="row.symbol">{{ row.symbol }}: {{ number(row.value) }} · {{ row.tradeDate || '—' }} · {{ row.source || '—' }}</span></div>
    <p class="hose-gap-note">{{ vi ? 'Chỉ số tham chiếu không phải cổ phiếu. Số liệu dưới đây giữ nguyên kỳ và phạm vi BCTC; không trộn số hợp nhất với riêng lẻ. Ngày công bố là mốc do nhà cung cấp báo, cần kiểm tra hồ sơ gốc.' : 'Reference indices are not equities. Figures retain their statement period and scope. Provider availability dates require verification against original filings.' }}</p>
    <div class="hose-metrics">
      <article v-for="row in evidence.metrics" :key="row.metric"><span>{{ label(row.metric) }}</span><strong>{{ number(row.value, row.unit) }}</strong><small v-if="row.growthPct != null">YoY: {{ number(row.growthPct, '%') }} <a v-for="(source, index) in row.growthSources" :key="index" :href="source.sourceUrl || undefined" target="_blank" rel="noopener noreferrer"> · {{ source.periodEnd }}</a></small><small>{{ row.status }} · {{ row.periodEnd || (vi ? 'Chưa có kỳ dữ liệu' : 'No data period') }} · {{ row.frequency }} · {{ row.reportScope }}</small><small>{{ row.source || '—' }} · {{ row.availableAt || '—' }} <a v-if="row.sourceUrl" :href="row.sourceUrl" target="_blank" rel="noopener noreferrer">{{ vi ? 'Kiểm chứng' : 'Verify' }}</a></small></article>
    </div>
    <h4>{{ vi ? 'Sự kiện / công bố đã thu thập' : 'Captured events / disclosures' }}</h4>
    <p v-if="!evidence.events.length">{{ vi ? 'Chưa có dữ liệu xác minh. Không đồng nghĩa với không có sự kiện.' : 'No verified data. This does not mean there are no events.' }}</p>
    <p v-for="(row, index) in evidence.events" :key="index">{{ row.title }} · {{ row.availableAt }} <a v-if="row.sourceUrl" :href="row.sourceUrl" target="_blank" rel="noopener noreferrer">{{ vi ? 'Nguồn' : 'Source' }}</a></p>
    <details><summary>{{ vi ? 'Khoảng trống dữ liệu và nguồn' : 'Data gaps and sources' }} ({{ evidence.dataGaps.length }})</summary><p v-for="(row, index) in evidence.dataGaps" :key="`gap-${index}`">{{ row.field }}: {{ row.reason }}</p><p v-for="(row, index) in evidence.sources" :key="`source-${index}`"><a v-if="row.url" :href="row.url" target="_blank" rel="noopener noreferrer">{{ row.provider }}</a><span v-else>{{ row.provider }}</span></p><small>{{ evidence.checksum }}</small></details>
  </section>
</template>

<script>
import { hoseResearchNumber } from '@/utils/hoseResearch'
const labels = { revenue: ['Doanh thu', 'Revenue'], total_operating_income: ['Thu nhập hoạt động (ngân hàng)', 'Bank operating income'], net_income: ['Lợi nhuận sau thuế', 'Net income'], operating_cash_flow: ['Dòng tiền hoạt động', 'Operating cash flow'], total_debt: ['Tổng nợ', 'Total debt'], shareholder_equity: ['Vốn chủ sở hữu', 'Shareholder equity'], earnings_per_share: ['EPS', 'EPS'], pe_ratio: ['P/E', 'P/E'], pb_ratio: ['P/B', 'P/B'] }
export default {
  name: 'HoseResearchEvidence',
  props: { evidence: { type: Object, default: null } },
  computed: { vi () { return this.$i18n.locale === 'vi-VN' } },
  methods: { number: hoseResearchNumber, label (metric) { return (labels[metric] || [metric, metric])[this.vi ? 0 : 1] } }
}
</script>

<style scoped>
.hose-research { margin:14px; padding:16px; color:var(--ink, #23334b); border:1px solid var(--line, #dce4ee); background:var(--card, #fff); border-radius:10px; } h3,h4 { color:inherit; margin:0 0 8px; } h4 { margin-top:14px; } p { font-size:12px; line-height:1.5; } small { color:var(--muted, #63738a); font-size:10px; overflow-wrap:anywhere; } .hose-price { display:grid; gap:4px; }.hose-price strong { font-size:20px; }.hose-price span, .hose-benchmarks { font-size:12px; }.hose-benchmarks { display:flex; gap:18px; flex-wrap:wrap; margin:12px 0; }.hose-gap-note { color:var(--muted, #63738a); }.hose-metrics { display:grid; gap:10px; grid-template-columns:repeat(3, minmax(0, 1fr)); } article { display:grid; gap:4px; padding:10px; border-radius:8px; background:var(--soft-blue, #f5f8fd); } article>span { font-size:11px; } article strong { font-size:15px; } details { margin-top:12px; } summary { cursor:pointer; font-size:12px; }
@media (max-width:640px) { .hose-metrics { grid-template-columns:1fr; } }
</style>
