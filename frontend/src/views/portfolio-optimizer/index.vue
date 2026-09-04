<template>
  <div class="optimizer-page" :class="{ 'theme-dark': isDarkTheme }" data-testid="portfolio-optimizer">
    <header class="workspace-header">
      <div>
        <h1>{{ $t('portfolioOptimizer.title') }}</h1>
        <p>{{ $t('portfolioOptimizer.subtitle') }}</p>
      </div>
      <div class="trust-tags" :aria-label="$t('portfolioOptimizer.safetyBoundaries')">
        <a-tag color="green">{{ $t('portfolioOptimizer.liveOnly') }}</a-tag>
        <a-tag color="blue">{{ $t('portfolioOptimizer.paperOnly') }}</a-tag>
        <a-tag>{{ $t('portfolioOptimizer.limit') }}</a-tag>
      </div>
    </header>

    <a-alert
      v-if="errorMessage"
      class="boundary-alert"
      type="error"
      show-icon
      closable
      :message="errorMessage"
      @close="errorMessage = ''"
    />

    <div class="workspace-grid">
      <a-card class="config-panel" :bordered="false">
        <h2>{{ $t('portfolioOptimizer.configuration') }}</h2>

        <a-form layout="vertical">
          <div class="field-grid">
            <a-form-item :label="$t('portfolioOptimizer.method')">
              <a-select v-model="form.method">
                <a-select-option v-for="item in methods" :key="item.value" :value="item.value">
                  {{ item.label }}
                </a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item :label="$t('portfolioOptimizer.baseCurrency')">
              <a-select v-model="form.baseCurrency">
                <a-select-option v-for="currency in currencies" :key="currency" :value="currency">
                  {{ currency }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </div>

          <a-form-item :label="$t('portfolioOptimizer.window')">
            <a-range-picker v-model="dateRange" class="full-width" :allow-clear="false" />
          </a-form-item>

          <a-form-item :label="$t('portfolioOptimizer.maxWeight')">
            <a-input-number
              v-model="form.maxWeightPct"
              class="full-width"
              :min="minimumMaxWeight"
              :max="100"
              :step="5"
              :formatter="value => `${value}%`"
              :parser="value => value.replace('%', '')"
            />
          </a-form-item>

          <a-form-item v-if="form.method === 'target_return'" :label="$t('portfolioOptimizer.targetReturn')">
            <a-input-number v-model="form.targetReturnPct" class="full-width" :min="-100" :max="500" :step="1" />
          </a-form-item>
          <a-form-item v-if="form.method === 'target_volatility'" :label="$t('portfolioOptimizer.targetVolatility')">
            <a-input-number v-model="form.targetVolatilityPct" class="full-width" :min="0.1" :max="500" :step="1" />
          </a-form-item>
          <a-form-item v-if="form.method === 'risk_tolerance'" :label="$t('portfolioOptimizer.riskTolerance')">
            <a-input-number v-model="form.riskTolerance" class="full-width" :min="0.1" :max="100" :step="0.1" />
          </a-form-item>

          <div class="instruments-heading">
            <h3>{{ $t('portfolioOptimizer.instruments') }}</h3>
            <span>{{ instruments.length }}/10</span>
          </div>

          <div class="instrument-list">
            <div v-for="(instrument, index) in instruments" :key="instrument.key" class="instrument-row">
              <a-select v-model="instrument.market" @change="onMarketChange(instrument)">
                <a-select-option value="Crypto">Crypto</a-select-option>
                <a-select-option value="VNStock">VN</a-select-option>
                <a-select-option value="Forex">XAU</a-select-option>
              </a-select>
              <div class="instrument-symbol-input">
                <CryptoAssetIcon
                  v-if="instrument.market"
                  :symbol="instrument.symbol"
                  :market="instrument.market"
                  :size="24"
                />
                <a-input v-model="instrument.symbol" :placeholder="$t('portfolioOptimizer.symbol')" />
              </div>
              <a-select v-model="instrument.currency">
                <a-select-option v-for="currency in currencies" :key="currency" :value="currency">
                  {{ currency }}
                </a-select-option>
              </a-select>
              <a-button
                type="link"
                :disabled="instruments.length <= 2"
                :aria-label="$t('portfolioOptimizer.remove')"
                @click="removeInstrument(index)"
              >
                <a-icon type="delete" />
              </a-button>
            </div>
          </div>

          <a-button
            class="add-button"
            block
            :disabled="instruments.length >= 10"
            @click="addInstrument"
          >
            <a-icon type="plus" /> {{ $t('portfolioOptimizer.addInstrument') }}
          </a-button>

          <a-button
            class="run-button"
            type="primary"
            block
            :loading="running"
            :disabled="!canRun"
            @click="runOptimizer"
          >
            {{ $t('portfolioOptimizer.run') }}
          </a-button>
        </a-form>
      </a-card>

      <main class="result-panel">
        <div v-if="!runResult && !running" class="empty-state">
          <a-icon type="fund" />
          <h2>{{ $t('portfolioOptimizer.result') }}</h2>
          <p>{{ $t('portfolioOptimizer.empty') }}</p>
        </div>
        <div v-else-if="running" class="result-skeleton" aria-live="polite">
          <a-skeleton active :paragraph="{ rows: 8 }" />
        </div>
        <template v-else>
          <section class="result-section">
            <div class="section-heading">
              <div>
                <h2>{{ $t('portfolioOptimizer.result') }}</h2>
                <code>{{ shortChecksum(runResult.inputChecksum) }}</code>
              </div>
              <a-tag color="green">{{ $t('portfolioOptimizer.liveTag') }}</a-tag>
            </div>

            <div class="metric-grid">
              <div><span>{{ $t('portfolioOptimizer.expectedReturn') }}</span><strong>{{ percent(runResult.expectedReturnPct) }}</strong></div>
              <div><span>{{ $t('portfolioOptimizer.volatility') }}</span><strong>{{ percent(runResult.volatilityPct) }}</strong></div>
              <div><span>{{ $t('portfolioOptimizer.sharpe') }}</span><strong>{{ number(runResult.sharpe) }}</strong></div>
              <div><span>{{ $t('portfolioOptimizer.observations') }}</span><strong>{{ runResult.observationCount }}</strong></div>
            </div>
          </section>

          <section class="result-section">
            <h3>{{ $t('portfolioOptimizer.allocation') }}</h3>
            <div class="allocation-list">
              <div v-for="item in runResult.allocations" :key="item.symbol" class="allocation-row">
                <span class="result-symbol-cell">
                  <CryptoAssetIcon
                    v-if="assetMarketForSymbol(item.symbol, item.market)"
                    :symbol="item.symbol"
                    :market="assetMarketForSymbol(item.symbol, item.market)"
                    :size="24"
                  />
                  <strong>{{ item.symbol }}</strong>
                </span>
                <div class="allocation-track" aria-hidden="true">
                  <span :style="{ width: `${item.weight * 100}%` }" />
                </div>
                <span>{{ percent(item.weight * 100) }}</span>
              </div>
            </div>
          </section>

          <section class="result-section">
            <h3>{{ $t('portfolioOptimizer.provenance') }}</h3>
            <a-table
              row-key="checksum"
              size="small"
              :pagination="false"
              :columns="provenanceColumns"
              :data-source="runResult.series || []"
              :scroll="{ x: 720 }"
            >
              <template slot="coverage" slot-scope="value">
                {{ percent(Number(value) * 100) }}
              </template>
              <template slot="provenanceSymbol" slot-scope="value, record">
                <span class="result-symbol-cell">
                  <CryptoAssetIcon
                    v-if="assetMarketForSymbol(value, record.market)"
                    :symbol="value"
                    :market="assetMarketForSymbol(value, record.market)"
                    :size="22"
                  />
                  <span>{{ value }}</span>
                </span>
              </template>
              <template slot="checksum" slot-scope="value">
                <code>{{ shortChecksum(value) }}</code>
              </template>
            </a-table>
          </section>

          <section class="result-section rebalance-section">
            <div>
              <h3>{{ $t('portfolioOptimizer.rebalance') }}</h3>
              <p>{{ $t('portfolioOptimizer.previewNote') }}</p>
            </div>
            <div class="preview-controls">
              <a-input-number
                v-model="portfolioValue"
                :min="1"
                :step="1000"
                :precision="2"
                :placeholder="$t('portfolioOptimizer.portfolioValue')"
              />
              <a-button :loading="previewing" @click="previewRebalance">
                {{ $t('portfolioOptimizer.preview') }}
              </a-button>
            </div>
          </section>

          <section v-if="preview" class="result-section proposal-section">
            <div class="section-heading">
              <h3>{{ $t('portfolioOptimizer.preview') }}</h3>
              <a-tag color="blue">{{ $t('portfolioOptimizer.simulatedTag') }}</a-tag>
            </div>
            <a-table
              row-key="symbol"
              size="small"
              :pagination="false"
              :columns="orderColumns"
              :data-source="preview.orders || []"
              :scroll="{ x: 720 }"
            >
              <template slot="orderSymbol" slot-scope="value, record">
                <span class="result-symbol-cell">
                  <CryptoAssetIcon
                    v-if="assetMarketForSymbol(value, record.market)"
                    :symbol="value"
                    :market="assetMarketForSymbol(value, record.market)"
                    :size="22"
                  />
                  <span>{{ value }}</span>
                </span>
              </template>
            </a-table>
            <a-button class="apply-button" type="primary" @click="confirmVisible = true">
              {{ $t('portfolioOptimizer.apply') }}
            </a-button>
          </section>

          <a-alert
            v-if="applyResult"
            type="success"
            show-icon
            :message="$t('portfolioOptimizer.applied')"
            :description="`${applyResult.transactionIds.length} SIMULATED transactions`"
          />
        </template>
      </main>
    </div>

    <a-modal
      :visible="confirmVisible"
      :confirm-loading="applying"
      :title="$t('portfolioOptimizer.confirmTitle')"
      :ok-text="$t('portfolioOptimizer.apply')"
      :wrap-class-name="isDarkTheme ? 'optimizer-confirm-modal theme-dark' : 'optimizer-confirm-modal'"
      @ok="applyRebalance"
      @cancel="confirmVisible = false"
    >
      <a-alert type="warning" show-icon :message="$t('portfolioOptimizer.confirmBody')" />
    </a-modal>
  </div>
</template>

<script>
import moment from 'moment'
import { mapState } from 'vuex'
import {
  applyOptimizerRun,
  createOptimizerRun,
  getOptimizerRun,
  previewOptimizerRun
} from '@/api/portfolio-optimizer'
import CryptoAssetIcon from '@/components/CryptoAssetIcon'

let instrumentKey = 0

function newInstrument (market = 'Crypto', symbol = '', currency = 'USDT') {
  instrumentKey += 1
  return { key: instrumentKey, market, symbol, currency }
}

export default {
  name: 'PortfolioOptimizer',
  components: { CryptoAssetIcon },
  data () {
    return {
      methods: [
        { value: 'risk_parity', label: 'Risk parity' },
        { value: 'minimum_variance', label: 'Minimum variance' },
        { value: 'maximum_sharpe', label: 'Maximum Sharpe' },
        { value: 'target_return', label: 'Target return' },
        { value: 'target_volatility', label: 'Target volatility' },
        { value: 'risk_tolerance', label: 'Risk tolerance' }
      ],
      currencies: ['USD', 'USDT', 'VND'],
      form: {
        method: 'minimum_variance',
        baseCurrency: 'USDT',
        maxWeightPct: 70,
        targetReturnPct: 10,
        targetVolatilityPct: 20,
        riskTolerance: 2
      },
      dateRange: [moment().subtract(1, 'year'), moment()],
      instruments: [newInstrument('Crypto', 'BTC/USDT', 'USDT'), newInstrument('Crypto', 'ETH/USDT', 'USDT')],
      running: false,
      previewing: false,
      applying: false,
      confirmVisible: false,
      runResult: null,
      preview: null,
      applyResult: null,
      portfolioValue: 10000,
      previewIdempotencyKey: '',
      errorMessage: ''
    }
  },
  computed: {
    ...mapState({ navTheme: state => state.app.theme }),
    isDarkTheme () {
      return this.navTheme === 'dark' || this.navTheme === 'realdark'
    },
    canRun () {
      return this.instruments.length >= 2 && this.instruments.every(item => item.market && item.symbol.trim() && item.currency)
    },
    minimumMaxWeight () {
      return Math.ceil(100 / Math.max(this.instruments.length, 1))
    },
    provenanceColumns () {
      return [
        { title: this.$t('portfolioOptimizer.symbol'), dataIndex: 'symbol', scopedSlots: { customRender: 'provenanceSymbol' }, width: 120 },
        { title: this.$t('portfolioOptimizer.provider'), dataIndex: 'provider', width: 170 },
        { title: this.$t('portfolioOptimizer.coverage'), dataIndex: 'coverage', scopedSlots: { customRender: 'coverage' }, width: 110 },
        { title: this.$t('portfolioOptimizer.checksum'), dataIndex: 'checksum', scopedSlots: { customRender: 'checksum' }, width: 160 }
      ]
    },
    orderColumns () {
      return [
        { title: this.$t('portfolioOptimizer.symbol'), dataIndex: 'symbol', scopedSlots: { customRender: 'orderSymbol' }, width: 110 },
        { title: this.$t('portfolioOptimizer.side'), dataIndex: 'side', width: 90 },
        { title: this.$t('portfolioOptimizer.weight'), dataIndex: 'targetWeightBps', customRender: value => this.percent(Number(value) / 100), width: 110 },
        { title: this.$t('portfolioOptimizer.quantity'), dataIndex: 'quantity', customRender: value => this.number(value, 6), width: 130 },
        { title: this.$t('portfolioOptimizer.markPrice'), dataIndex: 'markPrice', customRender: value => this.number(value, 4), width: 150 }
      ]
    }
  },
  methods: {
    addInstrument () {
      if (this.instruments.length < 10) this.instruments.push(newInstrument())
    },
    removeInstrument (index) {
      if (this.instruments.length > 2) {
        this.instruments.splice(index, 1)
        this.$nextTick(() => {
          if (this.form.maxWeightPct < this.minimumMaxWeight) {
            this.form.maxWeightPct = this.minimumMaxWeight
          }
        })
      }
    },
    onMarketChange (instrument) {
      if (instrument.market === 'Crypto') instrument.currency = 'USDT'
      if (instrument.market === 'VNStock') instrument.currency = 'VND'
      if (instrument.market === 'Forex') instrument.currency = 'USD'
    },
    payload () {
      return {
        method: this.form.method,
        baseCurrency: this.form.baseCurrency,
        startDate: this.dateRange[0].format('YYYY-MM-DD'),
        endDate: this.dateRange[1].format('YYYY-MM-DD'),
        maxWeight: Number(this.form.maxWeightPct) / 100,
        targetReturnPct: this.form.method === 'target_return' ? Number(this.form.targetReturnPct) : null,
        targetVolatilityPct: this.form.method === 'target_volatility' ? Number(this.form.targetVolatilityPct) : null,
        riskTolerance: this.form.method === 'risk_tolerance' ? Number(this.form.riskTolerance) : null,
        instruments: this.instruments.map(item => ({
          market: item.market,
          symbol: item.symbol.trim().toUpperCase(),
          currency: item.currency
        }))
      }
    },
    async runOptimizer () {
      this.running = true
      this.errorMessage = ''
      this.runResult = null
      this.preview = null
      this.applyResult = null
      this.previewIdempotencyKey = ''
      try {
        const created = await createOptimizerRun(this.payload())
        const details = await getOptimizerRun(created.data.id)
        this.runResult = {
          ...created.data,
          ...(details.data.result || {}),
          inputChecksum: details.data.inputChecksum,
          request: details.data.request,
          series: details.data.series || []
        }
      } catch (error) {
        this.errorMessage = this.errorText(error)
      } finally {
        this.running = false
      }
    },
    async previewRebalance () {
      if (!this.runResult) return
      this.previewing = true
      this.errorMessage = ''
      try {
        const response = await previewOptimizerRun(this.runResult.id, this.portfolioValue)
        this.preview = response.data
        this.previewIdempotencyKey = this.idempotencyKey()
      } catch (error) {
        this.errorMessage = this.errorText(error)
      } finally {
        this.previewing = false
      }
    },
    async applyRebalance () {
      if (!this.preview) return
      this.applying = true
      this.errorMessage = ''
      try {
        const response = await applyOptimizerRun(
          this.runResult.id,
          this.preview.id,
          this.previewIdempotencyKey
        )
        this.applyResult = response.data
        this.confirmVisible = false
      } catch (error) {
        this.errorMessage = this.errorText(error)
      } finally {
        this.applying = false
      }
    },
    idempotencyKey () {
      if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID()
      return `optimizer-${Date.now()}-${Math.random().toString(36).slice(2)}`
    },
    assetMarketForSymbol (symbol, market) {
      if (market && ['Crypto', 'VNStock', 'Forex'].includes(market)) return market
      const normalized = this.normalizeAssetSymbol(symbol)
      const instrument = this.instruments.find((item) => this.normalizeAssetSymbol(item.symbol) === normalized)
      return instrument ? instrument.market : ''
    },
    normalizeAssetSymbol (symbol) {
      return String(symbol || '').toUpperCase().split(/[_:-]/u)[0].split('/')[0]
    },
    errorText (error) {
      const message = String((error && error.message) || '')
      return /unavailable/i.test(message) ? this.$t('portfolioOptimizer.unavailable') : (message || this.$t('portfolioOptimizer.unavailable'))
    },
    shortChecksum (value) {
      const text = String(value || '')
      return text ? `${text.slice(0, 10)}...${text.slice(-6)}` : 'N/A'
    },
    percent (value) {
      const number = Number(value)
      return Number.isFinite(number) ? `${number.toFixed(2)}%` : 'N/A'
    },
    number (value, digits = 3) {
      const number = Number(value)
      return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : 'N/A'
    }
  }
}
</script>

<style lang="less" scoped>
.optimizer-page {
  min-height: calc(100vh - 64px);
  padding: 24px;
  color: #17202a;
  background: #f3f5f7;
}

.workspace-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  max-width: 1500px;
  margin: 0 auto 20px;

  h1 { margin: 0 0 6px; font-size: 30px; line-height: 1.2; }
  p { max-width: 720px; margin: 0; color: #64707d; }
}

.trust-tags { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.boundary-alert { max-width: 1500px; margin: 0 auto 16px; }
.workspace-grid { display: grid; grid-template-columns: minmax(320px, 390px) minmax(0, 1fr); gap: 20px; max-width: 1500px; margin: 0 auto; }
.config-panel, .result-panel, .result-section { border: 1px solid #dfe4e8; border-radius: 12px; background: #fff; }
.config-panel { align-self: start; box-shadow: 0 12px 30px rgba(34, 54, 74, .06); }
.config-panel h2, .result-panel h2, .result-panel h3 { color: inherit; }
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.full-width { width: 100%; }
.instruments-heading { display: flex; align-items: center; justify-content: space-between; margin: 6px 0 10px; }
.instruments-heading h3 { margin: 0; font-size: 15px; }
.instruments-heading span { color: #7b8793; font-variant-numeric: tabular-nums; }
.instrument-list { display: grid; gap: 8px; }
.instrument-row { display: grid; grid-template-columns: 92px minmax(90px, 1fr) 76px 34px; gap: 6px; align-items: center; }
.instrument-symbol-input { display: flex; min-width: 0; align-items: center; gap: 7px; }
.instrument-symbol-input .ant-input-wrapper, .instrument-symbol-input .ant-input { min-width: 0; flex: 1; }
.instrument-row .ant-btn { padding: 0; color: #8b96a1; }
.add-button { margin-top: 10px; border-style: dashed; }
.run-button { height: 42px; margin-top: 18px; font-weight: 600; }
.result-panel { min-height: 610px; padding: 20px; }
.empty-state { display: grid; place-items: center; align-content: center; min-height: 560px; text-align: center; color: #73808c; }
.empty-state .anticon { margin-bottom: 18px; font-size: 44px; color: #1677c8; }
.empty-state h2 { margin-bottom: 6px; }
.empty-state p { max-width: 460px; }
.result-skeleton { padding: 24px; }
.result-section { padding: 18px; margin-bottom: 14px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.section-heading h2, .section-heading h3 { margin: 0; }
.section-heading code, .result-section code { color: #61707d; font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; background: #e7ebef; }
.metric-grid > div { display: grid; gap: 5px; padding: 16px; background: #fff; }
.metric-grid span { color: #73808c; font-size: 12px; }
.metric-grid strong { font-size: 21px; font-variant-numeric: tabular-nums; }
.allocation-list { display: grid; gap: 13px; }
.allocation-row { display: grid; grid-template-columns: 100px minmax(100px, 1fr) 78px; gap: 12px; align-items: center; }
.result-symbol-cell { display: inline-flex; min-width: 0; align-items: center; gap: 7px; }
.allocation-row > span { text-align: right; font-variant-numeric: tabular-nums; }
.allocation-track { height: 8px; overflow: hidden; border-radius: 4px; background: #e8edf1; }
.allocation-track span { display: block; height: 100%; border-radius: inherit; background: #1677c8; transition: width .25s ease; }
.rebalance-section { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.rebalance-section h3 { margin: 0 0 4px; }
.rebalance-section p { margin: 0; color: #73808c; }
.preview-controls { display: flex; gap: 8px; }
.preview-controls .ant-input-number { width: 180px; }
.proposal-section .apply-button { display: block; margin: 16px 0 0 auto; }

.theme-dark {
  color: #e6edf3;
  background: #080c10;

  .workspace-header p, .rebalance-section p, .metric-grid span, .instruments-heading span { color: #8e9aa6; }
  .config-panel, .result-panel, .result-section { border-color: #27313b; background: #10161c; }
  .config-panel { box-shadow: none; }
  .metric-grid { background: #27313b; }
  .metric-grid > div { background: #10161c; }
  .allocation-track { background: #27313b; }
  .section-heading code, .result-section code { color: #9ba8b4; }
}

@media (max-width: 1050px) {
  .workspace-grid { grid-template-columns: 1fr; }
  .config-panel { position: static; }
}

@media (max-width: 700px) {
  .optimizer-page { padding: 14px; }
  .workspace-header { align-items: flex-start; flex-direction: column; }
  .trust-tags { justify-content: flex-start; }
  .field-grid, .metric-grid { grid-template-columns: 1fr 1fr; }
  .instrument-row { grid-template-columns: 82px minmax(80px, 1fr) 70px 30px; }
  .rebalance-section { align-items: stretch; flex-direction: column; }
  .preview-controls { flex-direction: column; }
  .preview-controls .ant-input-number { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .allocation-track span { transition: none; }
}
.allocation-row > .result-symbol-cell { text-align: left; }
.result-symbol-cell strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
