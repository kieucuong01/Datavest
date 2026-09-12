<template>
  <main class="guest-chart-page" :class="{ 'guest-chart-page--dark': isDark }">
    <section class="guest-chart-hero">
      <div>
        <span class="guest-chip"><a-icon type="eye" /> {{ $t('guest.indicatorReadOnly') }}</span>
        <h1>{{ $t('guest.indicatorTitle') }}</h1>
        <p>{{ $t('guest.indicatorDescription') }}</p>
      </div>
      <a-button type="primary" icon="lock" size="large" @click="openStrategyLogin">
        {{ $t('guest.strategyLogin') }}
      </a-button>
    </section>

    <section class="guest-chart-controls" aria-label="Market chart controls">
      <div class="control-group">
        <span>{{ $t('guest.asset') }}</span>
        <a-radio-group v-model="assetIndex" button-style="solid">
          <a-radio-button v-for="(asset, index) in assets" :key="asset.displaySymbol" :value="index">
            {{ asset.displaySymbol }}
          </a-radio-button>
        </a-radio-group>
      </div>
      <div class="control-group">
        <span>{{ $t('guest.timeframe') }}</span>
        <a-radio-group v-model="timeframe" button-style="solid">
          <a-radio-button v-for="item in timeframes" :key="item" :value="item">{{ item }}</a-radio-button>
        </a-radio-group>
      </div>
      <div class="market-identity">
        <strong>{{ selectedAsset.name }}</strong>
        <small>{{ selectedAsset.market }} · {{ selectedAsset.symbol }}</small>
      </div>
    </section>

    <section class="guest-chart-shell">
      <kline-chart
        :key="`${selectedAsset.market}:${selectedAsset.symbol}:${timeframe}`"
        :symbol="selectedAsset.symbol"
        :market="selectedAsset.market"
        :exchange-id="selectedAsset.exchangeId"
        :market-type="selectedAsset.marketType"
        :timeframe="timeframe"
        :theme="isDark ? 'dark' : 'light'"
        :active-indicators="activeIndicators"
        :realtime-enabled="selectedAsset.market === 'Crypto'"
        :full-width="true"
        :initial-limit="500"
        @indicator-toggle="handleIndicatorToggle"
      />
    </section>

    <section class="guest-chart-note">
      <a-icon type="info-circle" />
      <span>{{ $t('guest.indicatorNote') }}</span>
    </section>
  </main>
</template>

<script>
import { mapState } from 'vuex'
import KlineChart from '@/views/indicator-analysis/components/KlineChart'
import { loginTarget } from '@/utils/guestAccess'
import { applyIndicatorToggle, GUEST_ASSETS } from './guestIndicatorState'

export default {
  name: 'GuestIndicatorChart',
  components: { KlineChart },
  data () {
    return {
      assets: GUEST_ASSETS,
      assetIndex: 0,
      timeframe: '1H',
      timeframes: ['15m', '1H', '4H', '1D'],
      activeIndicators: [
        { id: 'ema', instanceId: 'guest-ema-20', params: { length: 20 }, visible: true },
        { id: 'rsi', instanceId: 'guest-rsi-14', params: { length: 14 }, visible: true }
      ]
    }
  },
  computed: {
    ...mapState({ navTheme: state => state.app.theme }),
    isDark () { return this.navTheme === 'dark' || this.navTheme === 'realdark' },
    selectedAsset () { return this.assets[this.assetIndex] || this.assets[0] }
  },
  methods: {
    handleIndicatorToggle (change) {
      this.activeIndicators = applyIndicatorToggle(this.activeIndicators, change)
    },
    openStrategyLogin () {
      this.$router.push(loginTarget('/strategy-ide'))
    }
  }
}
</script>

<style lang="less" scoped>
.guest-chart-page {
  min-height: calc(100vh - 64px);
  padding: 24px 28px 36px;
  color: #172033;
  background: #f5f7fb;
}
.guest-chart-hero, .guest-chart-controls, .guest-chart-shell, .guest-chart-note { width: 100%; max-width: 1540px; margin-right: auto; margin-left: auto; }
.guest-chart-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; }
.guest-chart-hero h1 { margin: 10px 0 5px; font-size: clamp(26px, 3vw, 38px); line-height: 1.1; }
.guest-chart-hero p { max-width: 720px; margin: 0; color: #68758a; font-size: 15px; }
.guest-chip { display: inline-flex; align-items: center; gap: 7px; color: #315ec9; font-size: 12px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.guest-chart-controls { display: flex; align-items: flex-end; gap: 24px; margin-top: 22px; padding: 16px 18px; border: 1px solid #dce3ee; border-radius: 14px 14px 0 0; background: #fff; }
.control-group { display: grid; gap: 7px; }.control-group > span { color: #6b7688; font-size: 11px; font-weight: 700; text-transform: uppercase; }
.market-identity { display: grid; gap: 2px; margin-left: auto; text-align: right; }.market-identity strong { font-size: 15px; }.market-identity small { color: #78869a; }
.guest-chart-shell { height: min(710px, calc(100vh - 310px)); min-height: 520px; overflow: hidden; border: 1px solid #dce3ee; border-top: 0; border-radius: 0 0 14px 14px; background: #fff; box-shadow: 0 14px 34px rgba(29, 54, 94, .08); }
.guest-chart-shell :deep(.kline-chart-wrapper) { height: 100%; }
.guest-chart-note { display: flex; gap: 8px; margin-top: 14px; color: #68758a; font-size: 13px; }
.guest-chart-page--dark { color: #eff4ff; background: #111827; }.guest-chart-page--dark .guest-chart-controls, .guest-chart-page--dark .guest-chart-shell { border-color: #2d394c; background: #182235; }.guest-chart-page--dark .guest-chart-hero p, .guest-chart-page--dark .market-identity small, .guest-chart-page--dark .guest-chart-note { color: #9eacc0; }
@media (max-width: 760px) { .guest-chart-page { padding: 16px 12px 24px; }.guest-chart-hero { align-items: stretch; flex-direction: column; }.guest-chart-hero .ant-btn { min-height: 44px; }.guest-chart-controls { align-items: stretch; flex-direction: column; gap: 14px; }.control-group .ant-radio-group { display: flex; overflow-x: auto; }.control-group .ant-radio-button-wrapper { flex: 0 0 auto; min-height: 44px; padding-top: 5px; }.market-identity { margin-left: 0; text-align: left; }.guest-chart-shell { height: 600px; min-height: 520px; } }
</style>
