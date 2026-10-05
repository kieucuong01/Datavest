<template>
  <section class="research-brief" aria-labelledby="research-brief-title">
    <header>
      <div><span class="brief-eyebrow">{{ vi ? 'Bản tóm tắt nghiên cứu' : 'Research decision brief' }}</span><h3 id="research-brief-title">{{ symbol }} · {{ day || '—' }}</h3></div>
      <div class="brief-horizon"><span>{{ vi ? 'Khung luận điểm' : 'Thesis horizon' }}</span><strong>{{ brief.timeHorizon || unavailable }}</strong></div>
      <button type="button" @click="$emit('open-full')">{{ vi ? 'Đọc báo cáo đầy đủ' : 'Read full report' }} →</button>
    </header>
    <p v-if="!validity.actionable" class="brief-expiry" role="status">{{ vi ? 'Cần đánh giá lại: bản này nằm ngoài kỳ hiệu lực hoặc chưa xác định được ngày. Các điều kiện dưới đây chưa được đối chiếu với diễn biến mới.' : 'Reassessment required: this report is outside its validity period or undated. Conditions below have not been checked against new developments.' }}</p>
    <p v-else class="brief-validity">{{ vi ? 'Kỳ hiệu lực đến' : 'Period valid until' }} {{ formatDate(validity.validUntil) }} · {{ vi ? 'Không bảo đảm điều kiện vô hiệu chưa xảy ra' : 'Does not verify that invalidation conditions remain untriggered' }}</p>
    <div class="brief-grid">
      <article class="brief-change">
        <h4>01 · {{ vi ? 'Điều gì thay đổi?' : 'What changed?' }}</h4>
        <p v-if="comparisonLoading">{{ vi ? 'Đang đối chiếu kỳ trước…' : 'Comparing the prior period…' }}</p>
        <p v-else-if="comparisonError">{{ vi ? 'Chưa đọc được báo cáo kỳ trước để đối chiếu.' : 'The prior report could not be read for comparison.' }} <button type="button" @click="$emit('retry-comparison')">{{ vi ? 'Thử lại' : 'Retry' }}</button></p>
        <template v-else-if="brief.comparison">
          <small>{{ vi ? 'So với báo cáo ngày' : 'Compared with' }} {{ brief.comparison.previousDate }}</small>
          <p v-if="brief.comparison.rating.changed !== null"><strong>{{ brief.comparison.rating.before }} → {{ brief.comparison.rating.after }}</strong><span> · {{ brief.comparison.rating.changed ? (vi ? 'Thay đổi nhận định' : 'Rating changed') : (vi ? 'Giữ nguyên nhận định' : 'Rating unchanged') }}</span></p>
          <p v-else>{{ vi ? 'Chưa đủ nhận định ở cả hai kỳ để so sánh.' : 'Both periods need a stated rating to compare.' }}</p>
          <p v-if="brief.comparison.timeHorizon.changed">{{ vi ? 'Khung thời gian' : 'Horizon' }}: {{ brief.comparison.timeHorizon.before }} → {{ brief.comparison.timeHorizon.after }}</p>
          <p v-if="brief.comparison.addedRisks.length">{{ vi ? 'Cách diễn đạt rủi ro mới' : 'New risk wording' }}: {{ brief.comparison.addedRisks[0].text }}</p>
          <p v-if="brief.comparison.removedRisks.length">{{ vi ? 'Không còn được nêu trong bản mới (chưa có nghĩa là đã hết rủi ro)' : 'No longer stated in the new report (not proof of resolution)' }}: {{ brief.comparison.removedRisks[0].text }}</p>
          <p v-if="brief.comparison.addedInvalidation.length">{{ vi ? 'Điều kiện vô hiệu bổ sung' : 'Additional invalidation wording' }}: {{ brief.comparison.addedInvalidation[0].text }}</p>
          <small>{{ vi ? 'Đối chiếu nội dung hai báo cáo; không phải đo lường hiệu quả đầu tư.' : 'Compares report text; not investment performance.' }}</small>
        </template>
        <p v-else>{{ vi ? 'Chưa có báo cáo kỳ trước cùng mã, ngôn ngữ và loại để đối chiếu. Không kết luận “không thay đổi”.' : 'No comparable prior report for this asset, language and report type. No unchanged claim is made.' }}</p>
        <p v-if="validity.actionable && brief.rating && !brief.comparison"><strong>{{ vi ? 'Nhận định trong báo cáo' : 'Report rating' }}: {{ brief.rating }}</strong></p>
      </article>
      <article>
        <h4>02 · {{ vi ? 'Bằng chứng & phản biện' : 'Evidence & counterarguments' }}</h4>
        <div v-for="group in evidenceGroups" :key="group.key" class="brief-evidence-group">
          <span class="brief-subheading">{{ group.label }}</span>
          <p v-if="!group.items.length" class="brief-missing">{{ unavailable }}</p>
          <ul v-else><li v-for="(item, index) in group.items.slice(0, 2)" :key="index"><span :title="item.text">{{ item.text }}</span><a v-if="item.sourceUrl" :href="item.sourceUrl" target="_blank" rel="noopener noreferrer">{{ vi ? 'Kiểm chứng nguồn' : 'Verify source' }} ↗</a><small v-else>{{ vi ? 'Dẫn lại báo cáo · chưa có liên kết gốc' : 'Report excerpt · no original link supplied' }}</small></li></ul>
        </div>
        <p v-if="!brief.supporting.length && brief.thesis.length" class="brief-missing"><strong>{{ vi ? 'Luận điểm chưa tách dữ kiện' : 'Thesis without separate evidence' }}:</strong> {{ brief.thesis[0].text }}</p>
      </article>
      <article class="brief-risk">
        <h4>03 · {{ vi ? 'Rủi ro chính' : 'Key risks' }}</h4>
        <p v-if="!brief.risks.length" class="brief-missing">{{ unavailable }} {{ vi ? 'Thiếu thông tin không có nghĩa là rủi ro thấp.' : 'Missing information does not mean low risk.' }}</p>
        <ul v-else><li v-for="(item, index) in brief.risks.slice(0, 3)" :key="index"><span :title="item.text">{{ item.text }}</span></li></ul>
        <p v-if="gapCount" class="brief-data-gap">{{ gapCount }} {{ vi ? 'khoảng trống dữ liệu của bản bằng chứng. Xem chi tiết trong phần đào sâu.' : 'evidence gaps. See details in the full report view.' }}</p>
      </article>
      <article class="brief-invalidation">
        <h4>04 · {{ vi ? 'Khi nào luận điểm vô hiệu?' : 'When is the thesis invalidated?' }}</h4>
        <p v-if="!brief.invalidation.length" class="brief-missing">{{ vi ? 'Báo cáo chưa nêu điều kiện vô hiệu cụ thể. Cần đọc phần quản trị rủi ro; không tự suy ra ngưỡng giá.' : 'The report supplies no explicit invalidation condition. Review risk management; no price threshold is inferred.' }}</p>
        <ul v-else><li v-for="(item, index) in brief.invalidation.slice(0, 3)" :key="index"><span :title="item.text">{{ item.text }}</span></li></ul>
        <p v-if="brief.scenarios.length" class="brief-scenario"><strong>{{ vi ? 'Kịch bản có điều kiện' : 'Conditional scenario' }}:</strong> {{ brief.scenarios[0].text }}</p>
      </article>
    </div>
    <footer><div><strong>{{ vi ? 'Theo dõi tiếp' : 'Watch next' }}</strong><span>{{ brief.watch.length ? brief.watch.slice(0, 2).map(item => item.text).join(' · ') : unavailable }}</span></div><small>{{ vi ? 'Trích từ cùng báo cáo. Bằng chứng do AI dẫn lại cần kiểm chứng; không hiển thị confidence như xác suất sinh lời. PDF giữ toàn bộ nội dung.' : 'Extracted from this report. AI evidence claims require verification; confidence is not a profit probability. The PDF retains all content.' }}</small></footer>
  </section>
</template>

<script>
import { buildResearchDecisionBrief, reportBriefDate } from '@/utils/researchDecisionBrief'
import { reportValidity } from '@/views/smart-insights/reportValidity'
import { formatVietnamDateTime } from '@/utils/vietnamTime'
export default {
  name: 'ResearchDecisionBrief',
  props: { report: { type: Object, required: true }, previousReport: { type: Object, default: null }, comparisonLoading: { type: Boolean, default: false }, comparisonError: { type: Boolean, default: false } },
  computed: {
    vi () { return this.$i18n.locale === 'vi-VN' },
    unavailable () { return this.vi ? 'Báo cáo chưa nêu / chưa có dữ liệu.' : 'Not stated / data unavailable.' },
    brief () { return buildResearchDecisionBrief(this.report, this.previousReport) },
    day () { return reportBriefDate(this.report) },
    symbol () { return this.report.displaySymbol || this.report.symbol || String(this.report.assetKey || '').split(':').pop() || '—' },
    validity () { return reportValidity(this.report) },
    gapCount () { return this.report.researchEvidence ? (this.report.researchEvidence.dataGaps || []).length : 0 },
    evidenceGroups () { return [{ key: 'supporting', label: this.vi ? 'Ủng hộ' : 'Supporting', items: this.brief.supporting }, { key: 'counter', label: this.vi ? 'Phản biện' : 'Counter', items: this.brief.counter }] }
  },
  methods: { formatDate (date) { return formatVietnamDateTime(date, { locale: this.vi ? 'vi-VN' : 'en-GB', fallback: '—' }) } }
}
</script>

<style scoped>
.research-brief { color:var(--ink, #21334c); background:var(--card, #fff); border:1px solid var(--line, #dae3ee); border-radius:12px; overflow:hidden; margin:14px 0; } header { display:flex; gap:18px; align-items:center; padding:16px 18px 10px; } h3 { color:inherit; font-size:20px; margin:3px 0 0; } .brief-eyebrow { color:var(--muted, #627189); font-size:11px; } .brief-horizon { margin-left:auto; display:grid; gap:4px; max-width:260px; font-size:12px; } .brief-horizon span { color:var(--muted, #627189); font-size:10px; } button { border:1px solid var(--line, #cbd9e9); border-radius:7px; background:var(--card, #fff); padding:8px 10px; color:var(--blue, #126bce); font-size:12px; cursor:pointer; } button:focus-visible { outline:2px solid #126bce; outline-offset:2px; }
.brief-validity,.brief-expiry { margin:0 18px 12px; font-size:10px; color:var(--muted, #627189); } .brief-expiry { padding:10px; color:#9b4d09; background:#fff5df; border-radius:6px; line-height:1.5; }.brief-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); border-top:1px solid var(--line, #dae3ee); }.brief-grid article { padding:14px 18px; min-width:0; border-bottom:1px solid var(--line, #dae3ee); }.brief-grid article:nth-child(odd) { border-right:1px solid var(--line, #dae3ee); } h4 { color:inherit; font-size:13px; margin:0 0 10px; } p,li { font-size:12px; line-height:1.5; margin:6px 0; overflow-wrap:anywhere; } small { font-size:10px; color:var(--muted, #627189); line-height:1.5; } ul { padding:0 0 0 15px; margin:5px 0; } li span { display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:3; overflow:hidden; } li a { color:var(--blue, #126bce); } li a,li small { display:block; font-size:10px; margin-top:3px; }.brief-subheading { font-size:10px; font-weight:700; color:var(--muted, #627189); }.brief-missing { color:var(--muted, #627189); }.brief-evidence-group+.brief-evidence-group { margin-top:10px; }.brief-data-gap { font-size:10px; }.brief-scenario { font-size:11px; }.brief-change>p { display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:3; overflow:hidden; }
footer { padding:12px 18px; display:grid; gap:8px; background:var(--soft-blue, #f5f8fd); } footer div { display:flex; gap:10px; font-size:11px; line-height:1.5; } footer strong { flex-shrink:0; } footer span { display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:2; overflow:hidden; }
@media (max-width:640px) { header { flex-wrap:wrap; padding:14px; }.brief-horizon { margin-left:0; } header button { width:100%; }.brief-grid { grid-template-columns:1fr; }.brief-grid article:nth-child(odd) { border-right:0; } footer div { display:grid; gap:3px; } }
</style>
