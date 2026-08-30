<template>
  <section class="live-data-sources" role="region" aria-labelledby="live-data-sources-title">
    <div class="live-data-sources-inner">
      <div class="live-data-heading">
        <span class="live-dot" :class="{ muted: !liveCount }" aria-hidden="true" />
        <div>
          <strong id="live-data-sources-title">{{ $t('smartInsights.liveDataSources') }}</strong>
          <small>{{ fetchedAtLabel }}</small>
        </div>
      </div>
      <div class="live-data-track">
        <div class="live-data-ticker-viewport">
          <div class="live-data-ticker-track" :class="{ 'is-animated': liveCount > 1 }">
            <div class="live-data-ticker-set">
              <article v-for="item in rows" :key="item.displaySymbol" class="live-asset-chip" :class="statusClass(item.status)">
                <strong class="asset-symbol">{{ item.displaySymbol }}</strong>
                <strong class="asset-price">{{ formatLiveAssetPrice(item.price, item.displaySymbol) }}</strong>
                <span :class="changeClass(item.changePercent)">{{ item.price === null ? '—' : signedPercent(item.changePercent) }}</span>
                <span class="asset-status">{{ statusLabel(item.status) }}</span>
                <small>{{ item.source || $t('smartInsights.dataUnavailableShort') }}</small>
              </article>
            </div>
            <div v-if="rows.length" class="live-data-ticker-set" aria-hidden="true">
              <article v-for="item in rows" :key="`clone-${item.displaySymbol}`" class="live-asset-chip" :class="statusClass(item.status)">
                <strong class="asset-symbol">{{ item.displaySymbol }}</strong>
                <strong class="asset-price">{{ formatLiveAssetPrice(item.price, item.displaySymbol) }}</strong>
                <span :class="changeClass(item.changePercent)">{{ item.price === null ? '—' : signedPercent(item.changePercent) }}</span>
                <span class="asset-status">{{ statusLabel(item.status) }}</span>
                <small>{{ item.source || $t('smartInsights.dataUnavailableShort') }}</small>
              </article>
            </div>
          </div>
          <div v-if="loading && !liveCount" class="live-data-empty">{{ $t('smartInsights.loading') }}</div>
          <div v-else-if="error && !liveCount" class="live-data-empty">{{ error }}</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import { formatLiveAssetPrice } from '../liveAssets'

export default {
  name: 'LiveDataSources',
  props: {
    rows: { type: Array, default: () => [] },
    fetchedAt: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    error: { type: String, default: '' }
  },
  computed: {
    liveCount () { return this.rows.filter(item => item && (item.status === 'LIVE' || item.status === 'STALE')).length },
    fetchedAtLabel () {
      if (!this.fetchedAt) return this.$t('smartInsights.waitingForData')
      const date = new Date(this.fetchedAt)
      return Number.isNaN(date.getTime()) ? this.fetchedAt : date.toLocaleTimeString(this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US')
    }
  },
  methods: {
    formatLiveAssetPrice,
    statusClass (status) { return `status-${String(status || 'UNAVAILABLE').toLowerCase()}` },
    statusLabel (status) {
      return ({ LIVE: this.$t('smartInsights.live'), STALE: this.$t('smartInsights.stale'), UNAVAILABLE: this.$t('smartInsights.unavailableShort') })[status] || this.$t('smartInsights.unavailableShort')
    },
    signedPercent (value) {
      const number = Number(value)
      if (!Number.isFinite(number)) return '—'
      return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`
    },
    changeClass (value) { return Number(value) >= 0 ? 'change-up' : 'change-down' }
  }
}
</script>

<style lang="less" scoped>
.live-data-sources { --ticker-ink: var(--ink, #17253d); --ticker-muted: var(--muted, #7b8798); --ticker-line: var(--line, #e4eaf3); --ticker-card: var(--card, #fff); width: 100%; overflow: hidden; border-bottom: 1px solid var(--ticker-line); background: var(--ticker-card); }
.live-data-sources-inner { display: flex; align-items: stretch; width: 100%; min-height: 46px; }
.live-data-heading { display: flex; align-items: center; gap: 8px; flex: 0 0 158px; padding: 6px 14px; border-right: 1px solid var(--ticker-line); }
.live-data-heading > div { display: grid; gap: 3px; min-width: 0; }
.live-data-heading strong { color: var(--ticker-ink); font-size: 12px; white-space: nowrap; }
.live-data-heading small { color: var(--ticker-muted); font-size: 11px; white-space: nowrap; }
.live-dot { width: 7px; height: 7px; flex: 0 0 auto; border-radius: 50%; background: #26b47d; box-shadow: 0 0 0 3px rgba(38,180,125,.12); }
.live-dot.muted { background: #aab4c3; box-shadow: none; }
.live-data-track { display: flex; align-items: center; flex: 1 1 auto; min-width: 0; }
.live-data-ticker-viewport { position: relative; width: 100%; overflow: hidden; }
.live-data-ticker-track { display: flex; width: max-content; min-width: 100%; }
.live-data-ticker-track.is-animated { animation: live-data-ticker-scroll 38s linear infinite; }
.live-data-ticker-set { display: flex; align-items: center; flex: 0 0 auto; }
.live-data-sources:hover .live-data-ticker-track.is-animated,
.live-data-sources:focus-within .live-data-ticker-track.is-animated { animation-play-state: paused; }
.live-asset-chip { display: flex; align-items: center; gap: 7px; min-width: 142px; height: 46px; padding: 0 14px; border-right: 1px solid var(--ticker-line); background: transparent; white-space: nowrap; }
.asset-symbol, .asset-price { color: var(--ticker-ink); font-size: 12px; font-variant-numeric: tabular-nums; }
.asset-price { font-size: 13px; }
.live-asset-chip > span { font-size: 11px; font-variant-numeric: tabular-nums; }
.live-asset-chip small { max-width: 84px; overflow: hidden; color: var(--ticker-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.asset-status { color: #1caa78; font-size: 10px !important; text-transform: uppercase; }
.status-stale .asset-status { color: #b78117; }
.status-unavailable .asset-status { color: var(--ticker-muted); }
.change-up { color: #1caa78; }
.change-down { color: #d55353; }
.live-data-empty { padding: 8px 0; color: var(--muted); font-size: 12px; white-space: nowrap; }
@keyframes live-data-ticker-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
@media (prefers-reduced-motion: reduce) { .live-data-ticker-track.is-animated { animation: none; } }
:global(body.dark) .live-data-sources,
:global(body.realdark) .live-data-sources,
:global(.basic-layout-wrapper.dark) .live-data-sources,
:global(.basic-layout-wrapper.realdark) .live-data-sources { --ticker-ink: #e9eff7; --ticker-muted: #9ba9ba; --ticker-line: #263341; --ticker-card: #121a23; }
@media (max-width: 680px) {
  .live-data-heading { flex-basis: 128px; padding-right: 10px; padding-left: 10px; }
  .live-data-heading strong { font-size: 11px; }
  .live-asset-chip { min-width: 126px; padding-right: 10px; padding-left: 10px; }
}
</style>
