<template>
  <section class="asset-opinions legacy-card" aria-labelledby="asset-opinions-title" :aria-busy="loading ? 'true' : 'false'">
    <div class="card-heading">
      <div class="heading-with-icon">
        <span class="section-icon brain-icon">✣</span>
        <div>
          <h2 id="asset-opinions-title">{{ $t('smartInsights.opinions') }}</h2>
          <p>{{ $t('smartInsights.watchlistOpinionsDesc') }}</p>
        </div>
      </div>
      <div class="heading-actions">
        <a-tag>{{ rows.length }} {{ $t('smartInsights.assets') }}</a-tag>
        <a-button size="small" icon="reload" :loading="loading" @click="$emit('refresh')">{{ $t('smartInsights.refresh') }}</a-button>
        <router-link class="watchlist-link" to="/ai-asset-analysis">{{ $t('smartInsights.manageWatchlist') }}</router-link>
      </div>
    </div>

    <div v-if="loading" class="opinion-loading" aria-live="polite">
      <a-skeleton active :paragraph="{ rows: 4 }" />
    </div>
    <div v-else-if="rows.length" class="opinion-table">
      <div class="opinion-table-head">
        <span>{{ $t('smartInsights.asset') }}</span>
        <span>{{ $t('smartInsights.latestAiAnalysis') }}</span>
        <span>{{ $t('smartInsights.dataStatus') }}</span>
        <span>{{ $t('smartInsights.actions') }}</span>
      </div>
      <div v-for="row in rows" :key="row.id" class="opinion-row">
        <div class="asset-cell">
          <span class="asset-avatar" :class="assetTone(row.displaySymbol)">{{ symbolMark(row.displaySymbol) }}</span>
          <span>
            <strong>{{ row.displaySymbol }}</strong>
            <small>{{ marketLabel(row.market) }}</small>
          </span>
        </div>
        <div>
          <template v-if="row.report">
            <a-tag :class="decisionTone(row.report.decision)">{{ decisionLabel(row.report.decision) }}</a-tag>
            <small class="muted-line">{{ row.report.summary || $t('smartInsights.aiReportUnavailable') }}</small>
            <small class="confidence-line">{{ $t('smartInsights.aiConfidence') }} {{ percent(row.report.confidence) }}</small>
          </template>
          <template v-else>
            <a-tag class="stance-neutral">{{ $t('smartInsights.dataUnavailableShort') }}</a-tag>
            <small class="muted-line">{{ $t('smartInsights.aiNoResult') }}</small>
          </template>
        </div>
        <small class="report-status">{{ row.report ? formatDateTime(row.report.createdAt) : $t('smartInsights.notAvailable') }}</small>
        <div class="opinion-actions">
          <a-button size="small" type="primary" icon="search" @click="$emit('open-analysis', row)">{{ $t('smartInsights.viewAnalysis') }}</a-button>
        </div>
      </div>
    </div>
    <div v-else class="legacy-empty table-empty">
      <a-icon type="star" />
      <div>
        <strong>{{ $t('smartInsights.watchlistOpinionsEmpty') }}</strong>
        <span>{{ $t('smartInsights.watchlistOpinionsEmptyDesc') }}</span>
        <router-link to="/ai-asset-analysis">{{ $t('smartInsights.manageWatchlist') }}</router-link>
      </div>
    </div>
  </section>
</template>

<script>
export default {
  name: 'AssetOpinionsSection',
  props: {
    rows: { type: Array, default: () => [] },
    mode: { type: String, default: 'live' },
    loading: { type: Boolean, default: false }
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
      return text === 'BUY' ? 'stance-positive' : text === 'SELL' ? 'stance-negative' : 'stance-neutral'
    },
    decisionLabel (decision) {
      const text = String(decision || '').toUpperCase()
      if (text === 'BUY') return this.$t('smartInsights.buy')
      if (text === 'SELL') return this.$t('smartInsights.sell')
      if (text === 'HOLD') return this.$t('smartInsights.neutral')
      return this.$t('smartInsights.notAvailable')
    },
    formatDateTime (value) {
      if (!value) return this.$t('smartInsights.notAvailable')
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return String(value)
      return date.toLocaleString(this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-GB', { dateStyle: 'short', timeStyle: 'short' })
    },
    marketLabel (market) {
      return ({ crypto: 'Crypto', vn: 'VN', us: 'US', gold: this.$t('smartInsights.gold') })[String(market || '').toLowerCase()] || String(market || '').toUpperCase()
    }
  }
}
</script>

<style lang="less" scoped>
.legacy-card { margin-top: 16px; overflow: hidden; border: 1px solid var(--line); border-radius: 12px; background: var(--card); box-shadow: 0 3px 12px var(--blue-ring); }
.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 17px; border-bottom: 1px solid var(--line); background: linear-gradient(var(--soft-blue), var(--card)); }
.heading-with-icon { display: flex; align-items: flex-start; gap: 9px; min-width: 0; }
.section-icon { display: inline-grid; place-items: center; flex: 0 0 auto; width: 30px; height: 30px; border-radius: 8px; color: #fff; background: var(--blue); font-size: 17px; font-weight: 700; }
.brain-icon { background: var(--blue-active); }
.card-heading h2 { margin: 0; color: var(--ink); font-size: 16px; line-height: 1.3; }
.card-heading p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
.heading-actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.heading-actions .ant-tag { margin: 0; font-size: 11px; }
.watchlist-link, .table-empty a { color: var(--blue); font-size: 12px; text-decoration: none; }
.opinion-loading { min-height: 170px; padding: 20px 18px; }
.opinion-table { width: 100%; }
.opinion-table-head, .opinion-row { display: grid; grid-template-columns: minmax(130px, 1.05fr) minmax(0, 2.35fr) minmax(90px, .85fr) minmax(112px, auto); align-items: center; gap: 12px; padding: 0 12px; }
.opinion-table-head > *, .opinion-row > * { min-width: 0; }
.opinion-table-head { min-height: 34px; color: var(--muted); border-bottom: 1px solid var(--line); background: var(--card); font-size: 11px; }
.opinion-row { min-height: 62px; border-bottom: 1px solid var(--line); font-size: 13px; }
.opinion-row:last-child { border-bottom: 0; }
.asset-cell { display: flex; align-items: center; gap: 8px; min-width: 0; }
.asset-cell > span:last-child { display: grid; gap: 2px; min-width: 0; }
.asset-cell strong { font-size: 13px; }
.asset-cell small, .muted-line { display: block; overflow: hidden; color: var(--muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.muted-line { display: -webkit-box; max-width: 100%; white-space: normal; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.asset-avatar { display: inline-grid; place-items: center; flex: 0 0 auto; width: 29px; height: 29px; border-radius: 50%; color: var(--blue); border: 1px solid var(--blue-ring); background: var(--soft-blue); font-size: 10px; font-weight: 800; }
.tone-btc { color: #9d6200; background: #fff3d7; }.tone-eth { color: #545bc3; background: #eff0ff; }.tone-xau { color: #8f6b00; background: #fff8d9; }.tone-vnix { color: #fff; background: #fa4865; }.tone-vn3 { color: #25324a; background: #eef1f7; }
.opinion-row .ant-tag { margin: 0 0 2px; font-size: 11px; }
.stance-positive { color: #1b9a6c; border-color: #a9e7cb; background: #e9fbf3; }.stance-negative { color: #d55353; border-color: #f0bcbc; background: #fff0f0; }.stance-neutral { color: #697689; border-color: #d4dce8; background: #f5f7fa; }
.confidence-line, .report-status { display: block; color: #7aa4de; font-size: 11px; }.report-status { color: var(--muted); overflow-wrap: anywhere; }.opinion-actions { display: flex; align-items: center; justify-content: flex-end; min-width: 0; }.opinion-actions .ant-btn { max-width: 100%; padding: 0 9px; overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.legacy-empty { display: flex; align-items: center; justify-content: center; gap: 9px; min-height: 94px; padding: 16px; color: var(--muted); text-align: center; }.legacy-empty div { display: grid; gap: 4px; text-align: left; }.legacy-empty span, .legacy-empty strong { font-size: 13px; }
.theme-dark & .card-heading { background: linear-gradient(var(--soft-blue), var(--card)); }.theme-dark & .opinion-table-head, .theme-dark & .opinion-row { border-color: var(--line); }.theme-dark & .opinion-table-head { background: var(--card); }
@media (max-width: 960px) { .opinion-table-head, .opinion-row { grid-template-columns: minmax(118px, 1fr) minmax(0, 1.6fr) minmax(76px, .72fr) minmax(108px, auto); } }
@media (max-width: 680px) { .card-heading { align-items: flex-start; flex-direction: column; }.heading-actions { justify-content: flex-start; }.opinion-table-head { display: none; }.opinion-row { grid-template-columns: 1fr auto; padding-top: 12px; padding-bottom: 10px; }.opinion-row > :nth-child(2) { grid-column: 1 / -1; }.opinion-row .opinion-actions { grid-column: 1 / -1; }.opinion-row .opinion-actions .ant-btn { width: 100%; } }
</style>
