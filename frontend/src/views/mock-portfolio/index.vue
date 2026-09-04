<template>
  <div class="mock-portfolio-page" :class="{ 'theme-dark': isDarkTheme }" data-testid="mock-portfolio">
    <header class="workspace-header">
      <div>
        <div class="eyebrow"><a-icon type="pie-chart" /> {{ $t('mockPortfolio.eyebrow') }}</div>
        <h1>{{ $t('mockPortfolio.title') }}</h1>
        <p>{{ $t('mockPortfolio.subtitle') }}</p>
      </div>
      <div class="header-actions">
        <a-tag class="simulation-tag" color="blue">{{ $t('mockPortfolio.simulated') }}</a-tag>
        <a-button icon="reload" :loading="loading" @click="loadData(true)">{{ $t('mockPortfolio.refresh') }}</a-button>
        <a-button type="primary" icon="plus" @click="openCreateModal">{{ $t('mockPortfolio.addPosition') }}</a-button>
      </div>
    </header>

    <a-alert
      v-if="errorMessage"
      class="page-alert"
      type="error"
      show-icon
      closable
      :message="errorMessage"
      @close="errorMessage = ''" />
    <a-alert class="paper-boundary" type="info" show-icon :message="$t('mockPortfolio.paperBoundary')" />

    <section class="portfolio-hero" aria-label="Portfolio overview">
      <div class="portfolio-left-column">
        <a-card class="surface-card balance-card" :bordered="false">
          <div class="card-topline">
            <span>{{ $t('mockPortfolio.totalBalance') }} <a-icon type="info-circle" /></span>
            <a-button type="primary" size="small" icon="plus" @click="openCreateModal">{{ $t('mockPortfolio.addPosition') }}</a-button>
          </div>
          <strong class="balance-number">{{ formatNumber(summary.total_market_value) }}</strong>
          <div class="pnl-pill" :class="summary.total_pnl >= 0 ? 'is-positive' : 'is-negative'">{{ signedPercent(summary.total_pnl_percent) }}</div>
          <span class="pnl-caption">{{ $t('mockPortfolio.metrics.pnl') }}: <b :class="summary.total_pnl >= 0 ? 'value-positive' : 'value-negative'">{{ signedNumber(summary.total_pnl) }}</b></span>
          <div class="balance-divider" />
          <div class="balance-details">
            <div><span>{{ $t('mockPortfolio.openCost') }}</span><strong>{{ formatNumber(summary.total_cost) }}</strong></div>
            <div><span>{{ $t('mockPortfolio.metrics.pnl') }}</span><strong :class="summary.total_pnl >= 0 ? 'value-positive' : 'value-negative'">{{ signedNumber(summary.total_pnl) }}</strong></div>
            <div><span>{{ $t('mockPortfolio.realizedPnl') }}</span><strong>—</strong></div>
          </div>
          <p class="source-note">{{ $t('mockPortfolio.metrics.sourceNote') }}</p>
        </a-card>

        <a-card class="surface-card allocation-card" :bordered="false">
          <div class="section-heading compact"><div><h2>{{ $t('mockPortfolio.allocationTitle') }}</h2><p>{{ $t('mockPortfolio.allocationSubtitle') }}</p></div></div>
          <div v-if="analytics.byCategory.length" class="allocation-body">
            <div ref="allocationChart" class="allocation-chart" role="img" :aria-label="$t('mockPortfolio.allocationTitle')" />
            <div class="allocation-legend"><div v-for="item in analytics.byCategory" :key="item.key" class="legend-row"><span class="legend-label"><i :style="{ background: item.color }" />{{ marketLabel(item.market) }}</span><strong>{{ item.allocation }}%</strong></div></div>
          </div>
          <a-empty v-else :description="$t('mockPortfolio.allocationEmpty')" :image="simpleEmptyImage" />
          <div v-if="analytics.bySymbol.length" class="symbol-allocation-list"><span v-for="item in analytics.bySymbol.slice(0, 6)" :key="`${item.market}-${item.symbol}`" class="symbol-allocation-chip"><CryptoAssetIcon v-if="isIdentityMarket(item.market)" :market="item.market" :symbol="item.symbol" :size="20" /><b>{{ item.symbol }}</b><em>{{ item.allocation }}%</em></span></div>
        </a-card>
      </div>

      <a-card class="surface-card performance-card" :bordered="false">
        <div class="section-heading performance-heading"><div><h2>{{ $t('mockPortfolio.performanceTitle') }}</h2><p>{{ $t('mockPortfolio.performanceSubtitle') }}</p></div><a-radio-group value="all" size="small" class="timeframe-controls"><a-radio-button value="1w">1W</a-radio-button><a-radio-button value="1m">1M</a-radio-button><a-radio-button value="ytd">YTD</a-radio-button><a-radio-button value="all">{{ $t('mockPortfolio.allTime') }}</a-radio-button></a-radio-group></div>
        <div class="performance-summary">
          <div class="comparison-tile"><span>{{ $t('mockPortfolio.currentPortfolio') }}</span><strong>{{ formatNumber(summary.total_market_value) }}</strong><small>{{ signedPercent(summary.total_pnl_percent) }}</small></div>
          <div class="comparison-tile muted"><span>{{ $t('mockPortfolio.benchmark') }}</span><strong>—</strong><small>{{ $t('mockPortfolio.historyUnavailable') }}</small></div>
          <div class="comparison-tile muted"><span>{{ $t('mockPortfolio.excessReturn') }}</span><strong>—</strong><small>{{ $t('mockPortfolio.historyUnavailable') }}</small></div>
        </div>
        <div class="performance-empty-state"><div class="chart-grid"><span v-for="line in 6" :key="line" /></div><div class="empty-message"><a-icon type="line-chart" /><strong>{{ $t('mockPortfolio.performanceEmptyTitle') }}</strong><p>{{ $t('mockPortfolio.performanceEmptyBody') }}</p></div></div>
        <p class="data-honesty-note"><a-icon type="safety-certificate" /> {{ $t('mockPortfolio.performanceDisclosure') }}</p>
      </a-card>
    </section>

    <a-card class="surface-card holdings-card" :bordered="false">
      <div class="section-heading"><div><h2>{{ $t('mockPortfolio.positionsTitle') }}</h2><p>{{ $t('mockPortfolio.positionsSubtitle') }}</p></div><span class="position-count">{{ positions.length }} {{ $t('mockPortfolio.assets') }}</span></div>
      <a-table
        v-if="positions.length"
        row-key="id"
        size="middle"
        :loading="loading"
        :pagination="false"
        :columns="columns"
        :data-source="positions"
        :scroll="{ x: 1120 }">
        <template slot="symbol" slot-scope="value, record"><div class="symbol-cell"><CryptoAssetIcon v-if="isIdentityMarket(record.market)" :market="record.market" :symbol="value" :size="26" /><span v-else class="asset-avatar">{{ assetInitial(value) }}</span><div><strong>{{ value }}</strong><small>{{ record.name || marketLabel(record.market) }}</small></div></div></template>
        <template slot="quantity" slot-scope="value">{{ formatNumber(value, 6) }}</template><template slot="entry_price" slot-scope="value">{{ formatNumber(value, 6) }}</template><template slot="current_price" slot-scope="value">{{ formatNumber(value, 6) }}</template><template slot="market_value" slot-scope="value">{{ formatNumber(value) }}</template>
        <template slot="allocation" slot-scope="_, record"><div class="allocation-bar"><span :style="{ width: `${allocationFor(record)}%` }" /></div><small>{{ allocationFor(record) }}%</small></template>
        <template slot="pnl" slot-scope="value, record"><span :class="value >= 0 ? 'value-positive' : 'value-negative'">{{ signedNumber(value) }}<small> {{ signedPercent(record.pnl_percent) }}</small></span></template>
        <template slot="signal" slot-scope="_, record"><a-tag :color="record.pnl >= 0 ? 'green' : 'red'">{{ record.pnl >= 0 ? $t('mockPortfolio.inProfit') : $t('mockPortfolio.inLoss') }}</a-tag></template>
        <template slot="actions" slot-scope="_, record"><a-button type="link" size="small" icon="edit" @click="openEditModal(record)" /><a-button type="link" size="small" icon="delete" class="delete-action" @click="confirmDelete(record)" /></template>
      </a-table>
      <a-empty v-else :description="$t('mockPortfolio.empty')"><a-button type="primary" icon="plus" @click="openCreateModal">{{ $t('mockPortfolio.addFirstPosition') }}</a-button></a-empty>
    </a-card>

    <section class="risk-section">
      <div class="risk-heading"><div><h2>{{ $t('mockPortfolio.riskTitle') }}</h2><p>{{ $t('mockPortfolio.riskSubtitle') }}</p></div><span>{{ $t('mockPortfolio.derivedFromPositions') }}</span></div>
      <div class="risk-grid"><div class="risk-card"><span>{{ $t('mockPortfolio.concentration') }}</span><strong>{{ analytics.concentration === null ? '—' : analytics.concentration.toFixed(3) }}</strong><small>{{ $t('mockPortfolio.concentrationHint') }}</small></div><div v-for="metric in unavailableRiskMetrics" :key="metric.key" class="risk-card unavailable"><span>{{ metric.label }}</span><strong>—</strong><small>{{ $t('mockPortfolio.historyUnavailable') }}</small></div></div>
    </section>

    <a-card class="surface-card transaction-card" :bordered="false"><div class="section-heading"><div><h2>{{ $t('mockPortfolio.transactionTitle') }}</h2><p>{{ $t('mockPortfolio.transactionSubtitle') }}</p></div><span class="position-count">0 {{ $t('mockPortfolio.transactions') }}</span></div><div class="transaction-empty"><a-icon type="database" /><div><strong>{{ $t('mockPortfolio.transactionEmptyTitle') }}</strong><p>{{ $t('mockPortfolio.transactionEmptyBody') }}</p></div></div></a-card>

    <a-modal
      :visible="modalVisible"
      :title="editingId ? $t('mockPortfolio.editTitle') : $t('mockPortfolio.addTitle')"
      :confirm-loading="saving"
      :ok-text="$t('mockPortfolio.save')"
      :cancel-text="$t('common.cancel')"
      :wrap-class-name="isDarkTheme ? 'mock-portfolio-modal theme-dark' : 'mock-portfolio-modal'"
      @ok="savePosition"
      @cancel="modalVisible = false">
      <a-form layout="vertical"><div class="form-grid"><a-form-item :label="$t('mockPortfolio.market')"><a-select v-model="form.market" :disabled="Boolean(editingId)" @change="onMarketChange"><a-select-option value="Crypto">{{ $t('mockPortfolio.markets.crypto') }}</a-select-option><a-select-option value="VNStock">{{ $t('mockPortfolio.markets.vn') }}</a-select-option><a-select-option value="Forex">{{ $t('mockPortfolio.markets.gold') }}</a-select-option></a-select></a-form-item><a-form-item :label="$t('mockPortfolio.symbol')"><a-input v-model="form.symbol" :disabled="Boolean(editingId)" :placeholder="symbolPlaceholder" /></a-form-item></div><div class="form-grid"><a-form-item :label="$t('mockPortfolio.side')"><a-select v-model="form.side" :disabled="Boolean(editingId)"><a-select-option value="long">{{ $t('mockPortfolio.long') }}</a-select-option><a-select-option value="short">{{ $t('mockPortfolio.short') }}</a-select-option></a-select></a-form-item><a-form-item :label="$t('mockPortfolio.quantity')"><a-input-number v-model="form.quantity" :min="0" :step="0.000001" class="full-width" /></a-form-item></div><div class="form-grid"><a-form-item :label="$t('mockPortfolio.entryPrice')"><a-input-number v-model="form.entry_price" :min="0" :step="0.01" class="full-width" /></a-form-item><a-form-item :label="$t('mockPortfolio.group')"><a-input v-model="form.group_name" :placeholder="$t('mockPortfolio.groupPlaceholder')" /></a-form-item></div><a-form-item :label="$t('mockPortfolio.notes')"><a-textarea v-model="form.notes" :rows="3" :placeholder="$t('mockPortfolio.notesPlaceholder')" /></a-form-item></a-form>
    </a-modal>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import * as echarts from 'echarts'
import { Empty } from 'ant-design-vue'
import { addPosition, deletePosition, getPositions, getPortfolioSummary, updatePosition } from '@/api/portfolio'
import { buildPortfolioAnalytics } from './portfolioAnalytics'
import CryptoAssetIcon from '@/components/CryptoAssetIcon'

const emptySummary = () => ({ total_market_value: 0, total_cost: 0, total_pnl: 0, total_pnl_percent: 0, position_count: 0, market_distribution: [] })
const emptyForm = () => ({ market: 'Crypto', symbol: 'BTC/USDT', name: '', side: 'long', quantity: null, entry_price: null, group_name: '', notes: '' })

export default {
  name: 'MockPortfolio',
  components: { CryptoAssetIcon },
  data () { return { loading: false, saving: false, modalVisible: false, editingId: null, positions: [], summary: emptySummary(), form: emptyForm(), errorMessage: '', allocationChartInstance: null } },
  computed: {
    ...mapState({ navTheme: state => state.app.theme }),
    isDarkTheme () { return this.navTheme === 'dark' || this.navTheme === 'realdark' },
    analytics () { return buildPortfolioAnalytics(this.positions) },
    simpleEmptyImage () { return Empty.PRESENTED_IMAGE_SIMPLE },
    unavailableRiskMetrics () { return [{ key: 'beta', label: this.$t('mockPortfolio.beta') }, { key: 'volatility', label: this.$t('mockPortfolio.volatility') }, { key: 'drawdown', label: this.$t('mockPortfolio.maxDrawdown') }, { key: 'var', label: this.$t('mockPortfolio.var95') }, { key: 'diversification', label: this.$t('mockPortfolio.diversification') }] },
    columns () {
      return [
        { title: this.$t('mockPortfolio.symbol'), dataIndex: 'symbol', scopedSlots: { customRender: 'symbol' }, width: 190 },
        { title: this.$t('mockPortfolio.quantity'), dataIndex: 'quantity', scopedSlots: { customRender: 'quantity' }, width: 110 },
        { title: this.$t('mockPortfolio.entryPrice'), dataIndex: 'entry_price', scopedSlots: { customRender: 'entry_price' }, width: 130 },
        { title: this.$t('mockPortfolio.currentPrice'), dataIndex: 'current_price', scopedSlots: { customRender: 'current_price' }, width: 130 },
        { title: this.$t('mockPortfolio.marketValue'), dataIndex: 'market_value', scopedSlots: { customRender: 'market_value' }, width: 135 },
        { title: this.$t('mockPortfolio.allocation'), key: 'allocation', scopedSlots: { customRender: 'allocation' }, width: 140 },
        { title: this.$t('mockPortfolio.pnl'), dataIndex: 'pnl', scopedSlots: { customRender: 'pnl' }, width: 150 },
        { title: this.$t('mockPortfolio.status'), key: 'signal', scopedSlots: { customRender: 'signal' }, width: 100 },
        { title: this.$t('mockPortfolio.actions'), key: 'actions', scopedSlots: { customRender: 'actions' }, fixed: 'right', width: 85 }
      ]
    },
    symbolPlaceholder () { return { Crypto: 'BTC/USDT', VNStock: 'FPT', Forex: 'XAUUSD' }[this.form.market] || 'BTC/USDT' }
  },
  watch: {
    positions: { deep: true, handler () { this.$nextTick(this.renderAllocationChart) } },
    isDarkTheme () { this.$nextTick(this.renderAllocationChart) }
  },
  created () { this.loadData() },
  mounted () { window.addEventListener('resize', this.resizeCharts) },
  beforeDestroy () { window.removeEventListener('resize', this.resizeCharts); if (this.allocationChartInstance) this.allocationChartInstance.dispose() },
  methods: {
    isIdentityMarket (market) { return ['crypto', 'vn', 'vnstock', 'vietnamstock', 'vietnam-stock', 'forex', 'gold', 'xau'].includes(String(market || '').toLowerCase()) },
    async loadData (refresh = false) {
      this.loading = true
      this.errorMessage = ''
      try {
        const params = refresh ? { refresh: true } : {}
        const [positionsResponse, summaryResponse] = await Promise.all([getPositions(params), getPortfolioSummary(params)])
        if (positionsResponse && positionsResponse.code !== 1) throw new Error(positionsResponse.msg || this.$t('mockPortfolio.loadFailed'))
        if (summaryResponse && summaryResponse.code !== 1) throw new Error(summaryResponse.msg || this.$t('mockPortfolio.loadFailed'))
        this.positions = positionsResponse && Array.isArray(positionsResponse.data) ? positionsResponse.data : []
        this.summary = summaryResponse && summaryResponse.data ? { ...emptySummary(), ...summaryResponse.data } : emptySummary()
      } catch (error) { this.errorMessage = error?.response?.data?.msg || error?.message || this.$t('mockPortfolio.loadFailed') } finally { this.loading = false }
    },
    renderAllocationChart () {
      if (!this.$refs.allocationChart || !this.analytics.byCategory.length) return
      if (!this.allocationChartInstance) this.allocationChartInstance = echarts.init(this.$refs.allocationChart)
      this.allocationChartInstance.setOption({ animationDuration: 350, tooltip: { trigger: 'item', valueFormatter: (value) => this.formatNumber(value) }, series: [{ type: 'pie', radius: ['58%', '80%'], center: ['50%', '50%'], avoidLabelOverlap: true, label: { show: false }, labelLine: { show: false }, itemStyle: { borderColor: this.isDarkTheme ? '#10161c' : '#fff', borderWidth: 5, borderRadius: 5 }, data: this.analytics.byCategory.map((item) => ({ value: item.marketValue, name: this.marketLabel(item.market), itemStyle: { color: item.color } })) }] }, true)
      this.allocationChartInstance.resize()
    },
    resizeCharts () { if (this.allocationChartInstance) this.allocationChartInstance.resize() },
    openCreateModal () { this.editingId = null; this.form = emptyForm(); this.modalVisible = true },
    openEditModal (position) { this.editingId = position.id; this.form = { market: position.market, symbol: position.symbol, name: position.name || '', side: position.side || 'long', quantity: Number(position.quantity || 0), entry_price: Number(position.entry_price || 0), group_name: position.group_name || '', notes: position.notes || '' }; this.modalVisible = true },
    onMarketChange () { if (this.form.market === 'Crypto') this.form.symbol = 'BTC/USDT'; if (this.form.market === 'VNStock') this.form.symbol = 'FPT'; if (this.form.market === 'Forex') this.form.symbol = 'XAUUSD' },
    async savePosition () {
      const quantity = Number(this.form.quantity || 0)
      const entryPrice = Number(this.form.entry_price || 0)
      if (!this.form.market || !this.form.symbol.trim() || quantity <= 0 || entryPrice <= 0) { this.errorMessage = this.$t('mockPortfolio.invalidValues'); return }
      this.saving = true
      this.errorMessage = ''
      try {
        const payload = { market: this.form.market, symbol: this.form.symbol.trim().toUpperCase(), name: this.form.name.trim(), side: this.form.side, quantity, entry_price: entryPrice, group_name: this.form.group_name.trim(), notes: this.form.notes.trim() }
        const response = this.editingId ? await updatePosition(this.editingId, payload) : await addPosition(payload)
        if (!response || response.code !== 1) throw new Error(response?.msg || this.$t('mockPortfolio.saveFailed'))
        this.modalVisible = false
        this.$message.success(this.$t(this.editingId ? 'mockPortfolio.updated' : 'mockPortfolio.created'))
        await this.loadData(true)
      } catch (error) { this.errorMessage = error?.response?.data?.msg || error?.message || this.$t('mockPortfolio.saveFailed') } finally { this.saving = false }
    },
    confirmDelete (position) { this.$confirm({ title: this.$t('mockPortfolio.deleteTitle'), content: `${this.$t('mockPortfolio.deleteBody')} ${position.symbol}?`, okText: this.$t('mockPortfolio.delete'), okType: 'danger', cancelText: this.$t('common.cancel'), onOk: () => this.removePosition(position) }) },
    async removePosition (position) { try { const response = await deletePosition(position.id); if (!response || response.code !== 1) throw new Error(response?.msg || this.$t('mockPortfolio.deleteFailed')); this.$message.success(this.$t('mockPortfolio.deleted')); await this.loadData(true) } catch (error) { this.errorMessage = error?.response?.data?.msg || error?.message || this.$t('mockPortfolio.deleteFailed') } },
    marketLabel (market) { return { Crypto: this.$t('mockPortfolio.markets.crypto'), VNStock: this.$t('mockPortfolio.markets.vn'), Forex: this.$t('mockPortfolio.markets.gold') }[market] || market },
    allocationFor (record) { const match = this.analytics.bySymbol.find((item) => item.symbol === String(record.symbol || '').toUpperCase() && item.market === record.market); return match ? match.allocation : 0 },
    assetInitial (symbol) { return String(symbol || '?').replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || '?' },
    formatNumber (value, digits = 2) { const number = Number(value); return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—' },
    signedNumber (value, digits = 2) { const number = Number(value); return Number.isFinite(number) ? `${number >= 0 ? '+' : ''}${this.formatNumber(number, digits)}` : '—' },
    signedPercent (value) { const number = Number(value); return Number.isFinite(number) ? `${number >= 0 ? '+' : ''}${number.toFixed(2)}%` : '—' }
  }
}
</script>

<style lang="less" scoped>
.mock-portfolio-page { min-height: calc(100vh - 64px); padding: 24px 28px 48px; color: #0f1b36; background: #f5f7fc; }
.workspace-header, .page-alert, .paper-boundary, .portfolio-hero, .holdings-card, .risk-section, .transaction-card { max-width: 1480px; margin-right: auto; margin-left: auto; }
.workspace-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 22px; margin-bottom: 17px; }.eyebrow { display: flex; align-items: center; gap: 7px; margin-bottom: 6px; color: #5d6c8c; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }h1 { margin: 0 0 6px; color: #06193a; font-size: 27px; font-weight: 800; letter-spacing: -.035em; }.workspace-header p { max-width: 700px; margin: 0; color: #66738f; font-size: 13px; }.header-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }.simulation-tag { font-size: 10px; font-weight: 800; letter-spacing: .06em; }.page-alert, .paper-boundary { margin-bottom: 12px; }
.portfolio-hero { display: grid; grid-template-columns: minmax(310px, .95fr) minmax(0, 1.65fr); gap: 16px; margin-bottom: 16px; }.portfolio-left-column { display: grid; gap: 16px; }.surface-card { overflow: hidden; border: 1px solid #dce4f1; border-radius: 12px; background: #fff; box-shadow: 0 10px 28px rgba(30, 53, 92, .05); }.balance-card { min-height: 210px; }.card-topline, .section-heading, .risk-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }.card-topline > span { color: #41506d; font-size: 12px; }.balance-number { display: block; margin-top: 11px; color: #071c40; font-size: clamp(28px, 3.5vw, 42px); font-variant-numeric: tabular-nums; letter-spacing: -.045em; }.pnl-pill { display: inline-flex; margin: 7px 7px 0 0; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }.pnl-pill.is-positive { color: #07833c; background: #e7f8ed; }.pnl-pill.is-negative { color: #c82942; background: #fff0f2; }.pnl-caption { color: #71809c; font-size: 11px; }.balance-divider { height: 1px; margin: 14px 0 11px; background: #dfe6f1; }.balance-details { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }.balance-details span, .risk-card span { display: block; margin-bottom: 4px; color: #7885a0; font-size: 10px; text-transform: uppercase; }.balance-details strong { font-size: 12px; font-variant-numeric: tabular-nums; }.source-note { margin: 12px 0 0; color: #8995aa; font-size: 10px; }
.section-heading { margin-bottom: 14px; }.section-heading.compact { margin-bottom: 6px; }.section-heading h2, .risk-heading h2 { margin: 0 0 3px; color: #142546; font-size: 16px; font-weight: 800; letter-spacing: -.02em; }.section-heading p, .risk-heading p { margin: 0; color: #6e7d99; font-size: 11px; }.allocation-card { min-height: 254px; }.allocation-body { display: grid; grid-template-columns: 1fr 1fr; align-items: center; min-height: 145px; }.allocation-chart { width: 100%; height: 150px; }.allocation-legend { display: grid; gap: 10px; padding-right: 8px; }.legend-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: #45536d; font-size: 12px; }.legend-label { display: inline-flex; align-items: center; gap: 7px; }.legend-label i { width: 8px; height: 8px; border-radius: 50%; }.legend-row strong { color: #182946; font-size: 12px; }.symbol-allocation-list { display: flex; flex-wrap: wrap; gap: 6px; padding-top: 10px; border-top: 1px solid #e4eaf3; }.symbol-allocation-chip { display: inline-flex; gap: 6px; padding: 4px 7px; border-radius: 5px; background: #f2f5fa; color: #42516d; font-size: 10px; }.symbol-allocation-chip em { color: #102858; font-style: normal; }
.performance-card { min-height: 480px; }.performance-heading { align-items: center; }.timeframe-controls { pointer-events: none; }.performance-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; margin-bottom: 18px; }.comparison-tile { min-height: 77px; padding: 11px 12px; border: 1px solid #cdd9ee; border-radius: 9px; background: #f8fbff; }.comparison-tile span { display: block; margin-bottom: 6px; color: #6c7a94; font-size: 10px; }.comparison-tile strong { display: block; color: #102754; font-size: 16px; font-variant-numeric: tabular-nums; }.comparison-tile small { display: block; margin-top: 4px; color: #40845d; font-size: 10px; }.comparison-tile.muted { border-color: #e3e8f1; background: #fbfcfe; }.comparison-tile.muted strong, .comparison-tile.muted small { color: #8793a9; }.performance-empty-state { position: relative; display: grid; min-height: 275px; place-items: center; overflow: hidden; border-radius: 8px; background: linear-gradient(180deg, #fbfcff, #f4f7fc); }.chart-grid { position: absolute; inset: 26px; display: grid; grid-template-rows: repeat(6, 1fr); }.chart-grid span { border-bottom: 1px solid rgba(117, 137, 170, .17); }.empty-message { position: relative; max-width: 320px; padding: 19px 22px; border: 1px solid #dce5f3; border-radius: 10px; background: rgba(255, 255, 255, .92); text-align: center; box-shadow: 0 8px 24px rgba(37, 66, 115, .05); }.empty-message .anticon { margin-bottom: 8px; color: #8ca0c2; font-size: 22px; }.empty-message strong { display: block; color: #324462; font-size: 14px; }.empty-message p { margin: 5px 0 0; color: #73819b; font-size: 11px; line-height: 1.55; }.data-honesty-note { margin: 11px 0 0; color: #6e7c95; font-size: 10px; }
.holdings-card, .transaction-card { margin-bottom: 22px; }.position-count { color: #77849e; font-size: 11px; }.symbol-cell { display: flex; align-items: center; gap: 8px; }.asset-avatar { display: inline-grid; width: 26px; height: 26px; place-items: center; border-radius: 50%; background: #e9effd; color: #1d53b4; font-size: 9px; font-weight: 800; }.symbol-cell strong, .symbol-cell small { display: block; }.symbol-cell strong { color: #13274f; font-size: 12px; }.symbol-cell small { color: #8290a8; font-size: 10px; }.allocation-bar { display: inline-block; width: 64px; height: 4px; overflow: hidden; border-radius: 4px; background: #e8edf5; vertical-align: middle; }.allocation-bar span { display: block; height: 100%; border-radius: inherit; background: #2055c6; }.allocation-bar + small { margin-left: 5px; color: #6f7d97; font-size: 10px; }.value-positive { color: #07833c; }.value-negative { color: #cf2946; }.value-positive small, .value-negative small { color: currentColor; font-size: 10px; }.delete-action { color: #cf2946; }
.risk-section { margin-bottom: 22px; }.risk-heading { margin-bottom: 10px; }.risk-heading > span { color: #8894aa; font-size: 9px; letter-spacing: .05em; text-transform: uppercase; }.risk-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }.risk-card { min-height: 82px; padding: 13px; border: 1px solid #dce4f1; border-radius: 10px; background: #fff; }.risk-card strong { color: #173469; font-size: 20px; font-variant-numeric: tabular-nums; }.risk-card small { display: block; margin-top: 4px; color: #8793aa; font-size: 9px; line-height: 1.35; }.risk-card.unavailable strong { color: #9ca7b9; }.transaction-empty { display: flex; align-items: center; gap: 13px; padding: 23px; border-top: 1px solid #e3e9f2; background: #fbfcff; }.transaction-empty .anticon { color: #8ba1c6; font-size: 23px; }.transaction-empty strong { color: #344563; font-size: 13px; }.transaction-empty p { margin: 4px 0 0; color: #71809a; font-size: 11px; }.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }.full-width { width: 100%; }
.theme-dark { color: #dce7f6; background: #080d16; h1, .balance-number, .section-heading h2, .risk-heading h2, .symbol-cell strong, .legend-row strong, .comparison-tile strong { color: #e6effc; }.workspace-header p, .section-heading p, .risk-heading p, .card-topline > span, .pnl-caption, .balance-details span, .risk-card span { color: #a1b0c7; }.surface-card, .risk-card { border-color: #28364d; background: #111a29; box-shadow: none; }.comparison-tile, .comparison-tile.muted { border-color: #2a3851; background: #141f30; }.performance-empty-state { background: linear-gradient(180deg, #121c2c, #0c1421); }.empty-message { border-color: #2b3a52; background: rgba(19, 30, 47, .94); }.empty-message strong, .transaction-empty strong { color: #dce7f6; }.symbol-allocation-list, .balance-divider, .transaction-empty { border-color: #28364d; }.symbol-allocation-chip { background: #1b2940; color: #b8c8df; }.symbol-allocation-chip em { color: #edf4ff; }.allocation-bar { background: #2b3a52; }.transaction-empty { background: #0e1725; } }
@media (max-width: 980px) { .mock-portfolio-page { padding: 20px 16px 34px; }.portfolio-hero { grid-template-columns: 1fr; }.risk-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }@media (max-width: 640px) { .workspace-header { align-items: flex-start; flex-direction: column; }.header-actions { justify-content: flex-start; }.performance-summary, .balance-details, .form-grid { grid-template-columns: 1fr; }.allocation-body { grid-template-columns: 1fr; }.allocation-legend { padding: 0 12px 12px; }.performance-card { min-height: 0; }.performance-empty-state { min-height: 230px; }.risk-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.risk-heading { align-items: flex-start; flex-direction: column; } }
.symbol-allocation-chip { align-items: center; }
</style>
