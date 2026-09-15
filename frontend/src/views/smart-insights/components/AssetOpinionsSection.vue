<template>
  <section class="asset-opinions opinion-card" aria-labelledby="asset-opinions-title" :aria-busy="loading ? 'true' : 'false'">
    <div class="card-heading">
      <div class="heading-with-icon">
        <span class="section-icon" aria-hidden="true"><a-icon type="bulb" /></span>
        <div>
          <h2 id="asset-opinions-title">{{ $t('smartInsights.opinions') }}</h2>
          <p>{{ guest ? $t('smartInsights.commonAssetOpinionsDesc') : $t('smartInsights.watchlistOpinionsDesc') }}</p>
        </div>
      </div>
      <div class="heading-actions">
        <a-tag class="asset-count"><strong>{{ rows.length }}</strong> {{ $t('smartInsights.assets') }}</a-tag>
        <a-button size="small" icon="reload" :loading="loading" @click="$emit('refresh')">{{ $t('smartInsights.refresh') }}</a-button>
        <router-link v-if="!guest" class="watchlist-link" to="/ai-asset-analysis">{{ $t('smartInsights.manageWatchlist') }}</router-link>
      </div>
    </div>

    <div v-if="loading" class="opinion-loading" aria-live="polite">
      <a-skeleton active :paragraph="{ rows: 4 }" />
    </div>
    <div v-else-if="rows.length" class="opinion-table">
      <div class="opinion-table-head" role="row">
        <span>{{ $t('smartInsights.asset') }}</span>
        <span>{{ $t('smartInsights.deepAnalysis') }}</span>
        <span>{{ $t('smartInsights.actions') }}</span>
      </div>

      <article
        v-for="row in rows"
        :key="row.id"
        class="opinion-row"
        role="row"
        :aria-label="`${row.displaySymbol} ${marketLabel(row.market)}`"
      >
        <div class="asset-cell" :data-label="$t('smartInsights.asset')">
          <CryptoAssetIcon
            v-if="isIdentityMarket(row.market)"
            :symbol="row.displaySymbol"
            :market="row.market"
            :size="36"
          />
          <span v-else class="asset-avatar" :class="assetTone(row.displaySymbol)">{{ symbolMark(row.displaySymbol) }}</span>
          <span class="asset-copy">
            <strong>{{ row.displaySymbol }}</strong>
            <small>{{ marketLabel(row.market) }}</small>
          </span>
        </div>

        <div class="opinion-main" :data-label="$t('smartInsights.deepAnalysis')">
          <div class="opinion-main-head">
            <span class="opinion-column-label">{{ $t('smartInsights.deepAnalysis') }}</span>
            <template v-if="row.researchInDevelopment">
              <a-tag class="stance-neutral">{{ $t('smartInsights.researchInDevelopment') }}</a-tag>
            </template>
          </div>
          <p v-if="row.researchInDevelopment" class="muted-line">{{ $t('smartInsights.researchInDevelopmentDesc') }}</p>
          <template v-else-if="researchReport(row)">
            <div class="decision-brief-grid">
              <div class="decision-brief-item decision-brief-item--rating">
                <span class="decision-brief-label">{{ $t('smartInsights.recommendation') }}</span>
                <strong class="decision-brief-rating" :class="decisionTone(decisionSummary(row).rating || researchReport(row).decision)">{{ reportDecisionLabel(row) }}</strong>
              </div>
              <div class="decision-brief-item decision-brief-item--horizon">
                <span class="decision-brief-label">{{ $t('smartInsights.timeHorizon') }}</span>
                <strong>{{ decisionSummary(row).timeHorizon || $t('smartInsights.notAvailable') }}</strong>
              </div>
              <div v-if="decisionActionPlan(row)" class="decision-brief-actions">
                <span class="decision-brief-section-label">{{ $t('smartInsights.decisionActionPlan') }}</span>
                <p class="decision-brief-action-copy">{{ decisionActionPlan(row) }}</p>
              </div>
            </div>
            <p v-if="!decisionActionPlan(row)" class="muted-line">{{ reportPreview(row) }}</p>
            <small v-if="reportCreatedAt(row)" class="decision-brief-created">{{ $t('smartInsights.reportCreatedAt') }}: {{ formatDateTime(reportCreatedAt(row)) }}</small>
          </template>
          <p v-else class="muted-line">{{ $t('smartInsights.deepAnalysisDesc') }}</p>
          <div v-if="row.researchInDevelopment" class="opinion-meta">
            <span class="engine-line"><a-icon type="tool" /> {{ $t('smartInsights.researchInDevelopment') }}</span>
          </div>
        </div>

        <div class="opinion-actions" :data-label="$t('smartInsights.actions')">
          <a-button v-if="row.researchInDevelopment" size="small" icon="tool" disabled class="deep-analysis-action">{{ $t('smartInsights.researchInDevelopment') }}</a-button>
          <a-button v-else-if="researchReport(row)" size="small" icon="file-text" class="deep-analysis-action" @click="$emit('open-deep-analysis', row)">{{ $t('smartInsights.viewDeepReport') }}</a-button>
          <a-button
            v-else-if="!guest && row.deepState && row.deepState.canCreate"
            size="small"
            type="primary"
            icon="apartment"
            class="deep-analysis-action"
            @click="$emit('create-deep-analysis', row)"
          >{{ $t('smartInsights.createDeepReport') }}</a-button>
          <span v-else class="opinion-action-empty" aria-hidden="true">—</span>
        </div>
      </article>
    </div>
    <div v-else class="legacy-empty table-empty">
      <a-icon type="star" />
      <div>
        <strong>{{ $t(guest ? 'smartInsights.commonAssetOpinionsEmpty' : 'smartInsights.watchlistOpinionsEmpty') }}</strong>
        <span>{{ $t(guest ? 'smartInsights.commonAssetOpinionsEmptyDesc' : 'smartInsights.watchlistOpinionsEmptyDesc') }}</span>
        <router-link v-if="!guest" to="/ai-asset-analysis">{{ $t('smartInsights.manageWatchlist') }}</router-link>
      </div>
    </div>
  </section>
</template>

<script>
import { formatVietnamDateTime } from '@/utils/vietnamTime'
import { extractPortfolioManagerDecisionSummary } from '@/utils/tradingAgentsReport'
import CryptoAssetIcon from '@/components/CryptoAssetIcon'

export default {
  name: 'AssetOpinionsSection',
  components: { CryptoAssetIcon },
  props: {
    rows: { type: Array, default: () => [] },
    mode: { type: String, default: 'live' },
    loading: { type: Boolean, default: false },
    guest: { type: Boolean, default: false }
  },
  methods: {
    percent (value) {
      const number = Number(value)
      return Number.isFinite(number) ? `${number.toFixed(0)}%` : this.$t('smartInsights.notAvailable')
    },
    symbolMark (symbol) { return String(symbol || '?').slice(0, 3).toUpperCase() },
    assetTone (symbol) { return `tone-${String(symbol || '').toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 4) || 'neutral'}` },
    decisionTone (decision) {
      const text = String(decision || '').toUpperCase()
      return ['BUY', 'OVERWEIGHT', 'ACCUMULATE', 'OUTPERFORM'].includes(text) ? 'stance-positive' : ['SELL', 'UNDERWEIGHT', 'REDUCE', 'UNDERPERFORM'].includes(text) ? 'stance-negative' : 'stance-neutral'
    },
    decisionLabel (decision) {
      const text = String(decision || '').toUpperCase()
      if (text === 'BUY') return this.$t('smartInsights.buy')
      if (text === 'SELL') return this.$t('smartInsights.sell')
      if (text === 'HOLD') return this.$t('smartInsights.neutral')
      if (['OVERWEIGHT', 'ACCUMULATE', 'OUTPERFORM'].includes(text)) return this.$t('smartInsights.overweight')
      if (['UNDERWEIGHT', 'REDUCE', 'UNDERPERFORM'].includes(text)) return this.$t('smartInsights.underweight')
      return this.$t('smartInsights.notAvailable')
    },
    researchReport (row) { return row && row.deepState && row.deepState.report ? row.deepState.report : null },
    decisionSummary (row) {
      const report = this.researchReport(row)
      if (!report) return { rating: '', timeHorizon: '', actions: [] }
      const empty = { rating: '', timeHorizon: '', actions: [] }
      const sources = [report.body, report.summary, report.title].filter(value => typeof value === 'string' && value.trim())
      return sources.reduce((summary, source) => {
        const parsed = extractPortfolioManagerDecisionSummary(source)
        return {
          rating: summary.rating || parsed.rating,
          timeHorizon: summary.timeHorizon || parsed.timeHorizon,
          actions: summary.actions.length ? summary.actions : parsed.actions
        }
      }, empty)
    },
    decisionActionPlan (row) {
      const actions = Array.isArray(this.decisionSummary(row).actions) ? this.decisionSummary(row).actions.filter(Boolean) : []
      return actions
        .map(action => String(action).trim().replace(/^(?:core strategy|capital management|stop-loss discipline|stop loss|add position(?:\/dca)? conditions|chiến lược cốt lõi|quản trị vốn|kỷ luật cắt lỗ|điều kiện mua thêm(?:\/dca)?)\s*:\s*/iu, '').trim())
        .filter(Boolean)
        .join(' ')
    },
    reportDecisionLabel (row) {
      const report = this.researchReport(row)
      const summary = this.decisionSummary(row)
      return summary.rating ? this.decisionLabel(summary.rating) : report && report.decision ? this.decisionLabel(report.decision) : this.$t('smartInsights.notAvailable')
    },
    reportPreview (row) {
      const report = this.researchReport(row)
      const value = report && (report.summary || report.title)
      return this.cleanPreview(value) || this.$t('smartInsights.deepReportReady')
    },
    cleanPreview (value) {
      return String(value || '')
        .replace(/\*\*(.*?)\*\*/gu, '$1')
        .replace(/__([^_]+)__/gu, '$1')
        .replace(/`([^`]+)`/gu, '$1')
        .replace(/\s+/gu, ' ')
        .trim()
    },
    reportCreatedAt (row) {
      const report = this.researchReport(row)
      return report && (report.createdAt || report.generatedAt || report.effectiveDate)
    },
    formatDateTime (value) {
      if (!value) return this.$t('smartInsights.notAvailable')
      return formatVietnamDateTime(value, { locale: this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-GB', fallback: String(value) })
    },
    isIdentityMarket (market) {
      return ['crypto', 'vn', 'vnstock', 'vietnamstock', 'vietnam-stock', 'forex', 'gold', 'xau'].includes(String(market || '').toLowerCase())
    },
    marketLabel (market) {
      return ({ crypto: 'Crypto', vn: 'VN', us: 'US', gold: this.$t('smartInsights.gold') })[String(market || '').toLowerCase()] || String(market || '').toUpperCase()
    }
  }
}
</script>

<style lang="less" scoped>
.opinion-card {
  --opinion-positive: #18794e;
  --opinion-positive-bg: #edf9f2;
  --opinion-positive-border: #b7e3c8;
  --opinion-negative: #b42318;
  --opinion-negative-bg: #fff2f0;
  --opinion-negative-border: #f1c0bb;
  --opinion-neutral: #56657a;
  --opinion-neutral-bg: #f5f7fa;
  --opinion-neutral-border: #d5dce6;
  margin-top: 18px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--card);
  box-shadow: 0 8px 22px var(--blue-ring);
}
.card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--line);
  background: linear-gradient(135deg, var(--soft-blue), var(--card) 72%);
}
.heading-with-icon { display: flex; align-items: flex-start; gap: 10px; min-width: 0; }
.section-icon { display: inline-grid; place-items: center; flex: 0 0 auto; width: 34px; height: 34px; border-radius: 9px; color: #fff; background: var(--blue-active); font-size: 16px; }
.card-heading h2 { margin: 0; color: var(--ink); font-size: 17px; line-height: 1.3; }
.card-heading p { margin: 4px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
.heading-actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.heading-actions .ant-tag { margin: 0; font-size: 11px; }.asset-count strong { color: var(--ink); font-size: 12px; }
.watchlist-link, .table-empty a { color: var(--blue); font-size: 12px; text-decoration: none; }.watchlist-link { padding: 7px 0; font-weight: 600; }
.watchlist-link:focus-visible, .table-empty a:focus-visible { outline: 2px solid var(--blue); outline-offset: 3px; border-radius: 4px; }
.opinion-loading { min-height: 180px; padding: 22px 20px; }.opinion-table { width: 100%; }
.opinion-table-head, .opinion-row { display: grid; grid-template-columns: minmax(112px, .55fr) minmax(0, 4fr) minmax(164px, .5fr); align-items: start; gap: 12px; padding: 0 20px; }
.opinion-table-head > *, .opinion-row > * { min-width: 0; }
.opinion-table-head { min-height: 38px; color: var(--muted); border-bottom: 1px solid var(--line); background: var(--card); font-size: 11px; font-weight: 600; }
.opinion-row { min-height: 104px; padding-top: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--line); font-size: 13px; transition: background-color .18s ease; }
.opinion-row:hover { background: var(--soft-blue); }.opinion-row:last-child { border-bottom: 0; }
.asset-cell { display: flex; align-items: center; gap: 10px; min-width: 0; }.asset-copy { display: grid; gap: 3px; min-width: 0; }
.asset-copy strong { color: var(--ink); font-size: 14px; letter-spacing: .01em; }.asset-copy small { color: var(--muted); font-size: 11px; }
.asset-avatar { display: inline-grid; place-items: center; flex: 0 0 auto; width: 36px; height: 36px; border-radius: 50%; color: var(--blue); border: 1px solid var(--blue-ring); background: var(--soft-blue); font-size: 10px; font-weight: 800; }
.tone-btc { color: #9d6200; background: #fff3d7; }.tone-eth { color: #545bc3; background: #eff0ff; }.tone-xau { color: #8f6b00; background: #fff8d9; }.tone-vnix { color: #fff; background: #fa4865; }.tone-vn3 { color: #25324a; background: #eef1f7; }
.opinion-main { min-width: 0; }.opinion-main-head { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-height: 0; }.opinion-column-label { display: none; color: var(--muted); font-size: 11px; font-weight: 700; }
.opinion-row .ant-tag { margin: 0; font-size: 11px; line-height: 20px; }.stance-positive { color: var(--opinion-positive); border-color: var(--opinion-positive-border); background: var(--opinion-positive-bg); }.stance-negative { color: var(--opinion-negative); border-color: var(--opinion-negative-border); background: var(--opinion-negative-bg); }.stance-neutral { color: var(--opinion-neutral); border-color: var(--opinion-neutral-border); background: var(--opinion-neutral-bg); }
.decision-brief-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 0; }.decision-brief-item, .decision-brief-actions { min-width: 0; padding: 9px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--card); color: var(--ink); font-size: 12px; font-weight: 600; line-height: 1.42; }.decision-brief-item { display: grid; align-content: start; gap: 4px; }.decision-brief-item--rating { background: var(--soft-blue); border-color: var(--blue-ring); }.decision-brief-actions { grid-column: 1 / -1; display: grid; gap: 8px; }.decision-brief-section-label { color: var(--ink); font-size: 10px; font-weight: 800; line-height: 1.2; text-transform: uppercase; letter-spacing: .06em; }.decision-brief-action-row { display: grid; grid-template-columns: minmax(116px, .46fr) minmax(0, 2fr); align-items: start; gap: 12px; }.decision-brief-action-row + .decision-brief-action-row { padding-top: 8px; border-top: 1px solid var(--line); }.decision-brief-label { color: var(--muted); font-size: 9px; font-weight: 750; line-height: 1.2; text-transform: uppercase; letter-spacing: .06em; }.decision-brief-rating { display: inline-flex; align-items: center; width: max-content; max-width: 100%; min-height: 24px; padding: 2px 9px; border: 1px solid transparent; border-radius: 999px; font-size: 11px; font-weight: 750; line-height: 1.35; }.decision-brief-created { display: block; margin-top: 7px; color: var(--muted); font-size: 10px; line-height: 1.35; }.opinion-main .muted-line { display: -webkit-box; max-width: 100%; margin: 6px 0 0; overflow: hidden; color: var(--ink); font-size: 12px; line-height: 1.5; text-overflow: ellipsis; white-space: normal; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }.opinion-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 7px; color: var(--muted); font-size: 10px; line-height: 1.35; }.engine-line, .confidence-line { display: inline-flex; align-items: center; gap: 4px; }.engine-line .anticon { color: var(--blue); }.confidence-line { color: var(--blue); }
.opinion-actions { display: flex; align-items: flex-start; justify-content: flex-end; flex-wrap: wrap; gap: 6px; min-width: 0; }.opinion-actions .ant-btn { min-height: 32px; padding: 0 8px; overflow: hidden; border-radius: 7px; font-size: 10px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; transition: transform .18s ease, box-shadow .18s ease; }.opinion-actions .ant-btn:hover { transform: translateY(-1px); }.opinion-actions .ant-btn:active { transform: scale(.98); }.deep-analysis-action { color: var(--blue); border-color: var(--blue-ring); background: transparent; }.opinion-action-empty { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; min-height: 32px; color: var(--muted); font-size: 14px; }
.decision-brief-item--rating, .decision-brief-item--horizon { min-height: 72px; }.decision-brief-item--rating { border-color: var(--blue); box-shadow: inset 3px 0 0 var(--blue); }.decision-brief-item--rating .decision-brief-rating { min-height: 30px; padding: 3px 11px; font-size: 13px; }.decision-brief-item--horizon strong { font-size: 13px; line-height: 1.35; }.decision-brief-action-copy { margin: 0; color: var(--ink); font-weight: 600; line-height: 1.5; }.opinion-actions .ant-btn { width: 100%; min-width: 0; overflow: visible; text-overflow: clip; }
.legacy-empty { display: flex; align-items: center; justify-content: center; gap: 9px; min-height: 110px; padding: 20px; color: var(--muted); text-align: center; }.legacy-empty div { display: grid; gap: 5px; text-align: left; }.legacy-empty span, .legacy-empty strong { font-size: 13px; }
.theme-dark & { --opinion-positive: #7bd99f; --opinion-positive-bg: rgba(82, 196, 26, .14); --opinion-positive-border: rgba(82, 196, 26, .38); --opinion-negative: #ff9c96; --opinion-negative-bg: rgba(255, 77, 79, .14); --opinion-negative-border: rgba(255, 77, 79, .38); --opinion-neutral: #b7c3d4; --opinion-neutral-bg: rgba(148, 163, 184, .14); --opinion-neutral-border: rgba(148, 163, 184, .38); }
@media (max-width: 1100px) { .opinion-table-head, .opinion-row { grid-template-columns: minmax(112px, .55fr) minmax(0, 3fr) minmax(160px, .5fr); gap: 10px; padding-right: 16px; padding-left: 16px; }.opinion-actions { justify-content: flex-start; } }
@media (max-width: 680px) {
  .card-heading { align-items: flex-start; flex-direction: column; gap: 13px; padding: 16px; }.heading-actions { width: 100%; justify-content: flex-start; }.opinion-table-head { display: none; }
  .opinion-row { display: flex; flex-direction: column; align-items: stretch; gap: 0; min-height: 0; padding: 16px; }.opinion-row > * { width: 100%; min-width: 0; }
  .asset-cell { padding-bottom: 12px; }.opinion-main { padding: 12px 0; border-top: 1px solid var(--line); }.opinion-column-label { display: inline-block; margin-right: auto; }.opinion-main-head { justify-content: flex-start; min-height: 25px; }.opinion-main .muted-line { -webkit-line-clamp: 4; }.opinion-meta { gap: 7px 12px; }
  .decision-brief-grid { grid-template-columns: 1fr; gap: 6px; }.decision-brief-item, .decision-brief-actions { padding: 8px; }.decision-brief-action-row { grid-template-columns: 1fr; gap: 4px; }.opinion-row .opinion-actions { display: grid; grid-template-columns: 1fr; gap: 8px; justify-content: stretch; width: 100%; padding-top: 12px; border-top: 1px solid var(--line); }.opinion-row .opinion-actions .ant-btn { width: 100%; min-height: 44px; font-size: 12px; }
}
@media (max-width: 480px) { .opinion-card { border-radius: 11px; }.heading-actions { gap: 7px; }.heading-actions .ant-btn { min-height: 40px; }.watchlist-link { width: 100%; padding: 4px 0; }.opinion-row { padding: 14px 12px; } }
@media (max-width: 380px) { .opinion-actions { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .opinion-row, .opinion-actions .ant-btn { transition: none; }.opinion-actions .ant-btn:hover, .opinion-actions .ant-btn:active { transform: none; } }
</style>
