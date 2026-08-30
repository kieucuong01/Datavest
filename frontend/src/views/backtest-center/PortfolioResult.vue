<template>
  <div class="portfolio-result" :class="{ 'theme-dark': isDark }">
    <div class="result-trustbar" :class="trustTone">
      <div>
        <a-icon :type="auditPassed ? 'check-circle' : 'warning'" />
        <strong>{{ statusLabel }}</strong>
        <span>{{ statusHint }}</span>
      </div>
      <div>
        <a-tag
          :color="auditPassed ? 'green' : 'red'"
          class="trust-tag"
          :class="auditPassed ? 'trust-tag--success' : 'trust-tag--error'">
          {{ auditPassed ? $t('strategyV2.backtest.auditPassed') : $t('strategyV2.backtest.auditFailed') }}
        </a-tag>
        <a-tag color="blue" class="trust-tag trust-tag--info">{{ $t('strategyV2.backtest.marketData') }}</a-tag>
        <a-tag
          v-if="legacyBackfilled"
          color="orange"
          class="trust-tag trust-tag--warning"
          :title="$t('strategyV2.backtest.legacyBackfillHint')">
          {{ $t('strategyV2.backtest.legacyBackfill') }}
        </a-tag>
      </div>
    </div>

    <a-alert
      v-if="result.liquidated"
      type="error"
      show-icon
      class="liquidation-alert"
      :message="$t('strategyV2.backtest.liquidatedTitle')"
      :description="$t('strategyV2.backtest.liquidatedHint')" />
    <a-alert
      v-else-if="result.legacyInsolventContinuation"
      type="error"
      show-icon
      class="liquidation-alert"
      :message="$t('strategyV2.backtest.legacyInsolventTitle')"
      :description="$t('strategyV2.backtest.legacyInsolventHint')" />

    <div class="metrics-grid">
      <div v-for="item in metrics" :key="item.key" class="metric-card">
        <span class="metric-label">
          {{ item.label }}
          <a-tooltip v-if="item.hint" :title="item.hint">
            <a-icon type="info-circle" />
          </a-tooltip>
        </span>
        <strong :class="item.tone">{{ item.value }}</strong>
      </div>
    </div>

    <section class="chart-card">
      <div class="chart-heading">
        <div>
          <h3>{{ $t('strategyV2.backtest.portfolioDashboard') }}</h3>
          <span>{{ benchmarkCaption }}</span>
        </div>
        <div class="chart-legend-note">{{ $t('strategyV2.backtest.chartInteractionHint') }}</div>
      </div>
      <div ref="chart" class="portfolio-chart" role="img" />
    </section>

    <div v-if="result.executionAssumptions" class="assumption-strip">
      <div><span>{{ $t('strategyV2.backtest.engine') }}</span><strong>{{ $t('strategyV2.backtest.engineV2') }}</strong></div>
      <div><span>{{ $t('strategyV2.backtest.fillRule') }}</span><strong>{{ $t('strategyV2.backtest.fillRuleNextOpen') }}</strong></div>
      <div><span>{{ $t('strategyV2.backtest.dateRange') }}</span><strong>{{ formatDateRange(result.executionAssumptions) }}</strong></div>
      <div><span>{{ $t('backtest-center.initialCapital') }}</span><strong>{{ formatNumber(result.executionAssumptions.initialCapital) }}</strong></div>
      <div><span>{{ $t('backtest-center.leverage') }}</span><strong>{{ formatLeverage(result.executionAssumptions) }}</strong></div>
      <div><span>{{ $t('backtest-center.commission') }}</span><strong>{{ formatRate(result.executionAssumptions.commission) }}</strong></div>
      <div><span>{{ $t('backtest-center.slippage') }}</span><strong>{{ formatRate(result.executionAssumptions.slippage) }}</strong></div>
      <div><span>{{ $t('trading-assistant.costs.funding') }}</span><strong>{{ $t('backtest-center.fundingNotModeled') }}</strong></div>
    </div>

    <a-tabs class="result-tabs" default-active-key="overview">
      <a-tab-pane key="overview" :tab="$t('strategyV2.backtest.tabs.overview')">
        <div class="overview-grid">
          <div class="overview-card">
            <span>{{ $t('strategyV2.backtest.latestCash') }}</span>
            <strong>{{ formatNumber(latestSnapshot.cash) }}</strong>
          </div>
          <div class="overview-card">
            <span>{{ $t('strategyV2.backtest.grossExposure') }}</span>
            <strong>{{ formatRate(latestSnapshot.grossExposure) }}</strong>
          </div>
          <div class="overview-card">
            <span>{{ $t('strategyV2.backtest.netExposure') }}</span>
            <strong>{{ formatRate(latestSnapshot.netExposure) }}</strong>
          </div>
          <div class="overview-card">
            <span>{{ $t('strategyV2.backtest.feeDrag') }}</span>
            <strong class="negative">{{ formatRate(attribution.feeDrag) }}</strong>
          </div>
        </div>
        <div class="status-grid">
          <div v-for="name in orderStatuses" :key="name" class="status-card" :class="`status-${name}`">
            <span>{{ $t(`strategyV2.backtest.orderStatus.${name}`) }}</span>
            <strong>{{ Number((attribution.orderStatus || {})[name] || 0) }}</strong>
          </div>
        </div>
      </a-tab-pane>

      <a-tab-pane key="rebalances" :tab="$t('strategyV2.backtest.tabs.rebalances')">
        <a-empty v-if="!rebalanceRows.length" :description="$t('strategyV2.backtest.noRebalances')" />
        <a-table
          v-else
          :columns="rebalanceColumns"
          :data-source="rebalanceRows"
          :row-key="row => row.time"
          size="small"
          :pagination="{ pageSize: 8 }"
          :scroll="{ x: 1100 }" />
      </a-tab-pane>

      <a-tab-pane key="holdings" :tab="$t('strategyV2.backtest.tabs.holdings')">
        <a-empty v-if="!holdingRows.length" :description="$t('strategyV2.backtest.noHoldings')" />
        <a-table
          v-else
          :columns="holdingColumns"
          :data-source="holdingRows"
          :row-key="(row, index) => `${row.time}-${row.symbol}-${index}`"
          size="small"
          :pagination="{ pageSize: 10 }"
          :scroll="{ x: 1050 }" />
      </a-tab-pane>

      <a-tab-pane key="closed" :tab="$t('strategyV2.backtest.tabs.tradesWithCount', { count: tradeRows.length })">
        <a-empty v-if="!tradeRows.length" :description="$t('strategyV2.backtest.noClosedTrades')" />
        <template v-else>
          <a-alert
            v-if="hasGridMatchedTrades"
            type="info"
            show-icon
            class="grid-accounting-alert"
            :message="$t('strategyV2.backtest.gridAccountingTitle')"
            :description="$t('strategyV2.backtest.gridAccountingHint')" />
          <a-table
            :columns="tradeColumns"
            :data-source="tradeRows"
            :row-key="(row, index) => row.id || index"
            :custom-row="tradeRowProps"
            size="small"
            :scroll="{ x: hasGridMatchedTrades ? 1850 : 1610 }"
            :pagination="{ pageSize: 8 }"
            class="clickable-table"
          />
        </template>
      </a-tab-pane>

      <a-tab-pane key="executions" :tab="$t('strategyV2.backtest.tabs.executionsWithCount', { count: executionRows.length })">
        <a-empty v-if="!executionRows.length" :description="$t('strategyV2.backtest.noExecutions')" />
        <a-table
          v-else
          :columns="executionColumns"
          :data-source="executionRows"
          :row-key="(row, index) => row.order_id || index"
          size="small"
          :scroll="{ x: 1250 }"
          :pagination="{ pageSize: 8 }" />
      </a-tab-pane>

      <a-tab-pane key="attribution" :tab="$t('strategyV2.backtest.tabs.attribution')">
        <a-table
          :columns="attributionColumns"
          :data-source="attribution.symbols || []"
          row-key="symbol"
          size="small"
          :pagination="false"
          :scroll="{ x: 900 }" />
      </a-tab-pane>

      <a-tab-pane key="audit" :tab="$t('strategyV2.backtest.tabs.audit')">
        <div class="audit-summary" :class="auditPassed ? 'passed' : 'failed'">
          <a-icon :type="auditPassed ? 'safety-certificate' : 'warning'" />
          <div><strong>{{ auditPassed ? $t('strategyV2.backtest.auditPassed') : $t('strategyV2.backtest.auditFailed') }}</strong><span>{{ $t('strategyV2.backtest.auditScope') }}</span></div>
        </div>
        <a-table
          :columns="ledgerColumns"
          :data-source="result.orderLedger || []"
          row-key="orderId"
          size="small"
          :pagination="{ pageSize: 10 }"
          :scroll="{ x: 1300 }" />
      </a-tab-pane>
    </a-tabs>

    <a-modal
      v-model="reviewVisible"
      :title="$t('strategyV2.backtest.tradeReviewTitle', { symbol: selectedTrade.symbol || '-' })"
      :footer="null"
      width="min(1440px, 94vw)"
      wrap-class-name="trade-review-modal"
      :destroy-on-close="true"
    >
      <div v-if="selectedTrade.symbol" class="review-summary">
        <span>{{ formatDate(selectedTrade.entry_time) }}</span>
        <strong>{{ formatNumber(selectedTrade.entry_price, 4) }}</strong>
        <a-icon type="arrow-right" />
        <span>{{ formatDate(selectedTrade.exit_time) }}</span>
        <strong>{{ formatNumber(selectedTrade.exit_price, 4) }}</strong>
        <b :class="profitTone(selectedTrade.profit)">{{ formatSignedNumber(selectedTrade.profit) }}</b>
      </div>
      <div class="review-chart-shell">
        <kline-chart
          v-if="reviewVisible"
          ref="reviewChart"
          :symbol="reviewInstrument.symbol"
          :market="reviewInstrument.market"
          :exchange-id="reviewInstrument.exchangeId"
          :market-type="reviewInstrument.marketType"
          :timeframe="reviewTimeframe"
          :initial-before-time="reviewWindow.beforeTime"
          :initial-limit="reviewWindow.limit"
          :theme="isDark ? 'dark' : 'light'"
          :active-indicators="[]"
          :realtime-enabled="false"
          :full-width="true"
          @load="renderReviewMarkers"
          @indicators-updated="renderReviewMarkers"
        />
      </div>
    </a-modal>
  </div>
</template>

<script>
import * as echarts from 'echarts'
import moment from 'moment'
import KlineChart from '@/views/indicator-analysis/components/KlineChart.vue'
import {
  buildTradeReviewWindow,
  calculateTradeValueUsd,
  findNearestBarIndex,
  resolveTradeReviewTimeframe
} from '@/utils/tradeReview'
import { timestampMillisecondsUtc } from '@/utils/utcInstant'
import { formatBacktestTime } from '@/utils/userTime'

export default {
  name: 'PortfolioResult',
  components: { KlineChart },
  props: {
    result: { type: Object, required: true },
    isDark: { type: Boolean, default: false }
  },
  data () {
    return {
      chart: null,
      resizeObserver: null,
      reviewVisible: false,
      selectedTrade: {},
      reviewMarkerTimer: null,
      orderStatuses: ['filled', 'partial', 'deferred', 'rejected']
    }
  },
  computed: {
    auditPassed () { return Boolean(this.result.audit && this.result.audit.passed) },
    legacyBackfilled () { return Boolean(this.result.compatibility && this.result.compatibility.legacyBackfill) },
    initialCapital () {
      return Number(
        this.result.initialCapital ||
        (this.result.executionAssumptions && this.result.executionAssumptions.initialCapital) ||
        0
      )
    },
    attribution () {
      const source = this.result.attribution && typeof this.result.attribution === 'object'
        ? this.result.attribution
        : {}
      const executions = this.result.executions || this.result.rawTrades || []
      const recordedCommission = Number(this.result.totalCommission)
      const totalCommission = Number.isFinite(recordedCommission)
        ? recordedCommission
        : executions.reduce((sum, item) => sum + Number(item.commission || 0), 0)
      const feeDrag = source.feeDrag !== undefined && source.feeDrag !== null
        ? source.feeDrag
        : (this.initialCapital > 0 ? totalCommission / this.initialCapital : 0)
      const savedStatuses = source.orderStatus && typeof source.orderStatus === 'object'
        ? source.orderStatus
        : null
      const orderStatus = savedStatuses || executions.reduce((counts, item) => {
        const status = this.orderStatuses.includes(item.status) ? item.status : 'filled'
        counts[status] += 1
        return counts
      }, { filled: 0, partial: 0, deferred: 0, rejected: 0 })
      return { ...source, feeDrag, orderStatus }
    },
    trustTone () {
      if (this.result.liquidated || this.result.legacyInsolventContinuation) return 'is-error'
      if (!this.auditPassed) return 'is-error'
      return this.result.resultStatus === 'completed_trades' ? 'is-success' : 'is-warning'
    },
    statusLabel () { return this.$t(`strategyV2.backtest.status.${this.result.resultStatus || 'unknown'}`) },
    statusHint () { return this.$t(`strategyV2.backtest.status.${this.result.resultStatus || 'unknown'}Hint`) },
    benchmarkCaption () {
      if (this.result.benchmarkStatus !== 'available') return this.$t('strategyV2.backtest.benchmarkUnavailable')
      const item = this.result.benchmark || {}
      return this.$t('strategyV2.backtest.comparedWith', { symbol: item.symbol || '-' })
    },
    metrics () {
      return [
        { key: 'return', label: this.$t('backtest-center.metrics.totalReturn'), value: this.formatPercent(this.result.totalReturn), tone: this.profitTone(this.result.totalReturn) },
        { key: 'benchmark', label: this.$t('strategyV2.backtest.benchmarkReturn'), value: this.result.benchmarkStatus === 'available' ? this.formatPercent(this.result.benchmarkTotalReturn) : '-', tone: this.profitTone(this.result.benchmarkTotalReturn) },
        { key: 'excess', label: this.$t('strategyV2.backtest.excessReturn'), value: this.result.benchmarkStatus === 'available' ? this.formatPercent(this.result.excessReturn) : '-', tone: this.profitTone(this.result.excessReturn) },
        { key: 'drawdown', label: this.$t('backtest-center.metrics.maxDrawdown'), value: this.formatPercent(this.result.maxDrawdown), tone: 'negative', hint: this.$t('strategyV2.backtest.maxDrawdownHint') },
        { key: 'executions', label: this.$t('strategyV2.backtest.executions'), value: Number(this.result.totalExecutions || 0), tone: '' },
        { key: 'trades', label: this.$t('strategyV2.backtest.closedTrades'), value: Number(this.result.totalTrades || 0), tone: '' },
        { key: 'win', label: this.$t('backtest-center.metrics.winRate'), value: this.formatPercent(this.result.winRate, false), tone: '' },
        { key: 'sharpe', label: this.$t('backtest-center.metrics.sharpe'), value: this.formatNumber(this.result.sharpeRatio), tone: '' }
      ]
    },
    latestSnapshot () {
      const snapshots = Array.isArray(this.result.holdingSnapshots) ? this.result.holdingSnapshots : []
      const rows = snapshots.length ? snapshots : (this.result.equityCurve || [])
      return rows[rows.length - 1] || {}
    },
    rebalanceRows () { return this.result.rebalanceRecords || [] },
    holdingRows () {
      return (this.result.holdingSnapshots || []).flatMap(snapshot => Object.keys(snapshot.positions || {}).map(symbol => ({ time: snapshot.time, symbol, ...snapshot.positions[symbol], cash: snapshot.cash, grossExposure: snapshot.grossExposure, netExposure: snapshot.netExposure }))).reverse()
    },
    tradeRows () { return this.result.closedTrades || this.result.trades || [] },
    hasGridMatchedTrades () {
      return this.tradeRows.some(row => row && row.profit_basis === 'grid_cell')
    },
    executionRows () { return this.result.executions || this.result.rawTrades || [] },
    reviewInstrument () {
      const raw = String(this.selectedTrade.symbol || '')
      const colon = raw.indexOf(':')
      const market = colon > -1 ? raw.slice(0, colon) : ''
      const rest = colon > -1 ? raw.slice(colon + 1) : raw
      const at = rest.lastIndexOf('@')
      const symbol = at > -1 ? rest.slice(0, at) : rest
      const suffix = at > -1 ? rest.slice(at + 1) : ''
      const parts = suffix.split(':')
      return { market, symbol, exchangeId: parts.length > 1 ? parts[0] : '', marketType: parts.length > 1 ? parts[1] : (parts[0] || 'spot') }
    },
    reviewTimeframe () {
      return resolveTradeReviewTimeframe(
        this.selectedTrade,
        (this.result.manifest && this.result.manifest.primaryFrequency) || '1d'
      )
    },
    reviewWindow () { return buildTradeReviewWindow(this.selectedTrade, this.reviewTimeframe) },
    rebalanceColumns () {
      return [
        { title: this.$t('strategyV2.backtest.time'), dataIndex: 'time', width: 170, customRender: this.formatDate },
        { title: this.$t('strategyV2.backtest.targetWeights'), dataIndex: 'targetWeights', width: 240, customRender: this.formatWeights },
        { title: this.$t('strategyV2.backtest.actualWeights'), dataIndex: 'actualWeights', width: 240, customRender: this.formatWeights },
        { title: this.$t('strategyV2.backtest.turnover'), dataIndex: 'turnover', customRender: this.formatRate },
        { title: this.$t('strategyV2.backtest.cashAfter'), dataIndex: 'cashAfter', customRender: value => this.formatNumber(value) },
        { title: this.$t('strategyV2.backtest.orderHealth'), key: 'health', customRender: (value, row) => `${row.filled || 0}/${row.partial || 0}/${row.deferred || 0}/${row.rejected || 0}` }
      ]
    },
    holdingColumns () {
      return [
        { title: this.$t('strategyV2.backtest.time'), dataIndex: 'time', width: 165, customRender: this.formatDate },
        { title: this.$t('backtest-center.symbol'), dataIndex: 'symbol', width: 170 },
        { title: this.$t('backtest-center.quantity'), dataIndex: 'quantity', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t('strategyV2.backtest.averageCost'), dataIndex: 'averageCost', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t('strategyV2.backtest.marketValue'), dataIndex: 'marketValue', customRender: value => this.formatNumber(value) },
        { title: this.$t('strategyV2.backtest.weight'), dataIndex: 'weight', customRender: this.formatRate },
        { title: this.$t('strategyV2.backtest.cash'), dataIndex: 'cash', customRender: value => this.formatNumber(value) }
      ]
    },
    tradeColumns () {
      const columns = [
        { title: this.$t('backtest-center.symbol'), dataIndex: 'symbol', width: 165 },
        { title: this.$t('backtest-center.tradeColumns.side'), dataIndex: 'side', width: 72 },
        { title: this.$t('backtest-center.tradeColumns.entryTime'), dataIndex: 'entry_time', width: 165, customRender: this.formatDate },
        { title: this.$t('backtest-center.tradeColumns.exitTime'), dataIndex: 'exit_time', width: 165, customRender: this.formatDate },
        { title: this.$t('backtest-center.tradeColumns.quantity'), dataIndex: 'quantity', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t('backtest-center.tradeColumns.valueUsd'), key: 'value_usd', customRender: (value, row) => this.formatNullableNumber(calculateTradeValueUsd(row)) },
        { title: this.$t(this.hasGridMatchedTrades ? 'strategyV2.backtest.gridMatchedEntry' : 'backtest-center.tradeColumns.entryPrice'), dataIndex: 'entry_price', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t('backtest-center.tradeColumns.exitPrice'), dataIndex: 'exit_price', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t('trading-assistant.costs.openingCommission'), dataIndex: 'entry_commission', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t('trading-assistant.costs.closingCommission'), dataIndex: 'exit_commission', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t(this.hasGridMatchedTrades ? 'strategyV2.backtest.gridMatchedProfit' : 'backtest-center.tradeColumns.profit'), dataIndex: 'profit', customRender: value => this.$createElement('span', { class: ['trade-profit', this.profitTone(value)] }, this.formatSignedNumber(value)) },
        { title: this.$t('backtest-center.tradeColumns.balance'), dataIndex: 'balance', customRender: value => this.formatNumber(value) },
        { title: this.$t('backtest-center.tradeColumns.closeReason'), dataIndex: 'close_reason', width: 150 }
      ]
      if (this.hasGridMatchedTrades) {
        columns.splice(8, 0, {
          title: this.$t('strategyV2.backtest.accountAverageEntry'),
          dataIndex: 'account_avg_entry_price',
          customRender: value => this.formatNullableNumber(value === undefined ? null : value, 4)
        })
        columns.splice(columns.length - 2, 0, {
          title: this.$t('strategyV2.backtest.accountRealizedProfit'),
          dataIndex: 'account_realized_profit',
          customRender: value => value === undefined || value === null
            ? '-'
            : this.$createElement('span', { class: ['trade-profit', this.profitTone(value)] }, this.formatSignedNumber(value))
        })
      }
      return columns
    },
    executionColumns () {
      return [
        { title: this.$t('strategyV2.backtest.signalTime'), dataIndex: 'signal_time', width: 165, customRender: this.formatDate },
        { title: this.$t('strategyV2.backtest.fillTime'), dataIndex: 'time', width: 165, customRender: this.formatDate },
        { title: this.$t('backtest-center.symbol'), dataIndex: 'symbol', width: 165 },
        { title: this.$t('strategyV2.backtest.side'), dataIndex: 'side', width: 70 },
        { title: this.$t('backtest-center.quantity'), dataIndex: 'quantity', customRender: value => this.formatNumber(value, 6) },
        { title: this.$t('backtest-center.price'), dataIndex: 'price', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t('strategyV2.backtest.filledNotional'), dataIndex: 'notional', customRender: (value, row) => this.formatNumber(value !== undefined && value !== null ? value : Number(row.quantity || 0) * Number(row.price || 0)) },
        { title: this.$t('backtest-center.commission'), dataIndex: 'commission', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t('strategyV2.backtest.orderStatusLabel'), dataIndex: 'status' },
        { title: this.$t('strategyV2.backtest.reason'), dataIndex: 'reason', width: 145 }
      ]
    },
    attributionColumns () {
      return [
        { title: this.$t('backtest-center.symbol'), dataIndex: 'symbol', width: 180 },
        { title: this.$t('strategyV2.backtest.industry'), dataIndex: 'industry' },
        { title: this.$t('strategyV2.backtest.realizedProfit'), dataIndex: 'realizedProfit', customRender: value => this.signedCell(value) },
        { title: this.$t('strategyV2.backtest.unrealizedProfit'), dataIndex: 'unrealizedProfit', customRender: value => this.signedCell(value) },
        { title: this.$t('backtest-center.commission'), dataIndex: 'commission', customRender: value => this.formatNumber(value) },
        { title: this.$t('strategyV2.backtest.netContribution'), dataIndex: 'netContribution', customRender: value => this.signedPercentCell(value) }
      ]
    },
    ledgerColumns () {
      return [
        { title: this.$t('strategyV2.backtest.time'), dataIndex: 'eventTime', width: 165, customRender: this.formatDate },
        { title: this.$t('backtest-center.symbol'), dataIndex: 'symbol', width: 165 },
        { title: this.$t('strategyV2.backtest.orderStatusLabel'), dataIndex: 'status', width: 90, customRender: value => this.$createElement('a-tag', { props: { color: this.statusColor(value) } }, this.$t(`strategyV2.backtest.orderStatus.${value}`)) },
        { title: this.$t('strategyV2.backtest.statusReason'), dataIndex: 'statusReason', width: 180, customRender: this.formatStatusReason },
        { title: this.$t('strategyV2.backtest.requestedQuantity'), dataIndex: 'requestedQuantity', customRender: value => this.formatNumber(value, 6) },
        { title: this.$t('strategyV2.backtest.filledQuantity'), dataIndex: 'filledQuantity', customRender: value => this.formatNumber(value, 6) },
        { title: this.$t('backtest-center.price'), dataIndex: 'price', customRender: value => this.formatNumber(value, 4) },
        { title: this.$t('strategyV2.backtest.filledNotional'), key: 'filledNotional', customRender: (value, row) => this.formatNumber(Number(row.filledQuantity || 0) * Number(row.price || 0)) },
        { title: this.$t('strategyV2.backtest.attempt'), dataIndex: 'attempt' }
      ]
    }
  },
  watch: {
    result: { deep: true, handler () { this.$nextTick(this.renderChart) } },
    isDark () { this.$nextTick(this.renderChart) }
  },
  mounted () { this.renderChart(); window.addEventListener('resize', this.resizeChart) },
  beforeDestroy () {
    window.removeEventListener('resize', this.resizeChart)
    if (this.reviewMarkerTimer) clearTimeout(this.reviewMarkerTimer)
    if (this.resizeObserver) this.resizeObserver.disconnect()
    if (this.chart) this.chart.dispose()
  },
  methods: {
    renderChart () {
      const curve = this.result.equityCurve || []
      if (!this.$refs.chart || !curve.length) return
      if (!this.chart) {
        this.chart = echarts.init(this.$refs.chart)
        if (typeof ResizeObserver !== 'undefined') {
          this.resizeObserver = new ResizeObserver(this.resizeChart)
          this.resizeObserver.observe(this.$refs.chart)
        }
      }
      const firstValue = Number(curve[0].value || 0)
      const base = this.initialCapital > 0 ? this.initialCapital : (firstValue > 0 ? firstValue : 1)
      let peak = base
      const normalized = curve.map(item => [timestampMillisecondsUtc(item.time), Number(item.value) / base * 100])
      const drawdown = curve.map(item => {
        const value = Number(item.value)
        peak = Math.max(peak, value)
        const savedDrawdown = Number(item.drawdown)
        const pointDrawdown = item.drawdown !== undefined && item.drawdown !== null && Number.isFinite(savedDrawdown)
          ? savedDrawdown
          : ((value / peak - 1) * 100)
        return [timestampMillisecondsUtc(item.time), pointDrawdown]
      })
      const benchmarkRaw = this.result.benchmarkCurve || []
      const benchmarkBase = benchmarkRaw.length ? Number(benchmarkRaw[0].value || 1) : 1
      const benchmark = benchmarkRaw.map(item => [timestampMillisecondsUtc(item.time), Number(item.value) / benchmarkBase * 100])
      const cash = curve.map(item => [timestampMillisecondsUtc(item.time), Number(item.cash || 0)])
      const gross = curve.map(item => [timestampMillisecondsUtc(item.time), Number(item.grossExposure || 0) * 100])
      const net = curve.map(item => [timestampMillisecondsUtc(item.time), Number(item.netExposure || 0) * 100])
      const text = this.isDark ? '#8c8c8c' : '#64748b'
      const grid = this.isDark ? '#242424' : '#e8edf3'
      const strategyName = this.$t('strategyV2.backtest.strategyNormalized')
      const benchmarkName = this.$t('strategyV2.backtest.benchmarkNormalized')
      this.chart.setOption({
        animationDuration: 260,
        color: ['#52c41a', '#f5a623', '#ff4d4f', '#69c0ff', '#9254de', '#13c2c2'],
        legend: { top: 2, left: 8, textStyle: { color: text } },
        tooltip: { trigger: 'axis', confine: true, axisPointer: { type: 'cross', snap: true }, backgroundColor: this.isDark ? 'rgba(14,14,14,.98)' : '#fff', borderColor: grid, textStyle: { color: this.isDark ? '#f5f5f5' : '#1f2937' } },
        axisPointer: { link: [{ xAxisIndex: [0, 1, 2] }] },
        grid: [
          { left: 58, right: 56, top: 42, height: 245 },
          { left: 58, right: 56, top: 325, height: 92 },
          { left: 58, right: 56, top: 455, height: 92 }
        ],
        xAxis: [0, 1, 2].map((value, index) => ({ type: 'time', gridIndex: index, axisLabel: { show: index === 2, color: text }, axisLine: { lineStyle: { color: grid } }, splitLine: { show: false } })),
        yAxis: [
          { type: 'value', gridIndex: 0, scale: true, name: this.$t('strategyV2.backtest.normalizedBase'), nameTextStyle: { color: text }, axisLabel: { color: text }, splitLine: { lineStyle: { color: grid, type: 'dashed' } } },
          { type: 'value', gridIndex: 1, max: 0, name: this.$t('strategyV2.backtest.drawdown'), nameTextStyle: { color: text }, axisLabel: { color: text, formatter: '{value}%' }, splitLine: { lineStyle: { color: grid, type: 'dashed' } } },
          { type: 'value', gridIndex: 2, name: this.$t('strategyV2.backtest.exposure'), nameTextStyle: { color: text }, axisLabel: { color: text, formatter: '{value}%' }, splitLine: { lineStyle: { color: grid, type: 'dashed' } } },
          { type: 'value', gridIndex: 2, position: 'right', name: this.$t('strategyV2.backtest.cash'), nameTextStyle: { color: text }, axisLabel: { color: text }, splitLine: { show: false } }
        ],
        dataZoom: [{ type: 'inside', xAxisIndex: [0, 1, 2], filterMode: 'none' }, { type: 'slider', xAxisIndex: [0, 1, 2], bottom: 0, height: 22, showDetail: false }],
        series: [
          { name: strategyName, type: 'line', data: normalized, xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, lineStyle: { width: 2.2 }, areaStyle: { opacity: 0.06 } },
          { name: benchmarkName, type: 'line', data: benchmark, xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, lineStyle: { width: 1.6, type: 'dashed' } },
          { name: this.$t('strategyV2.backtest.drawdown'), type: 'line', data: drawdown, xAxisIndex: 1, yAxisIndex: 1, showSymbol: false, areaStyle: { opacity: 0.22 }, lineStyle: { width: 1.4 } },
          { name: this.$t('strategyV2.backtest.grossExposure'), type: 'line', data: gross, xAxisIndex: 2, yAxisIndex: 2, showSymbol: false },
          { name: this.$t('strategyV2.backtest.netExposure'), type: 'line', data: net, xAxisIndex: 2, yAxisIndex: 2, showSymbol: false },
          { name: this.$t('strategyV2.backtest.cash'), type: 'line', data: cash, xAxisIndex: 2, yAxisIndex: 3, showSymbol: false, lineStyle: { type: 'dotted' } }
        ]
      }, true)
    },
    resizeChart () { if (this.chart) this.chart.resize() },
    tradeRowProps (record) { return { on: { click: () => { this.selectedTrade = record; this.reviewVisible = true } } } },
    renderReviewMarkers () {
      if (this.reviewMarkerTimer) clearTimeout(this.reviewMarkerTimer)
      this.reviewMarkerTimer = setTimeout(() => {
        const component = this.$refs.reviewChart
        const chart = component && component.getChartInstance ? component.getChartInstance() : null
        const trade = this.selectedTrade || {}
        const entryTime = this.reviewWindow.entryTime
        const exitTime = this.reviewWindow.exitTime
        const entryPrice = Number(trade.entry_price)
        const exitPrice = Number(trade.exit_price)
        if (!component || !chart || !Number.isFinite(entryTime) || !Number.isFinite(exitTime)) return

        component.clearBacktestOverlays()
        const isShort = String(trade.side || '').toLowerCase() === 'short'
        if (Number.isFinite(entryPrice)) {
          component.addBacktestOverlay(this.reviewMarkerConfig({
            timestamp: entryTime,
            price: entryPrice,
            text: this.$t('strategyV2.backtest.entryMarker'),
            side: isShort ? 'sell' : 'buy',
            color: isShort ? '#f6465d' : '#0ecb81'
          }))
        }
        if (Number.isFinite(exitPrice)) {
          component.addBacktestOverlay(this.reviewMarkerConfig({
            timestamp: exitTime,
            price: exitPrice,
            text: this.$t('strategyV2.backtest.exitMarker'),
            side: isShort ? 'buy' : 'sell',
            color: isShort ? '#0ecb81' : '#f6465d'
          }))
        }
        this.focusReviewRange(chart, entryTime, exitTime)
      }, 80)
    },
    reviewMarkerConfig ({ timestamp, price, text, side, color }) {
      return {
        name: 'signalTag',
        points: [{ timestamp, value: price }, { timestamp, value: price }],
        extendData: { text, side, color, source: 'backtest', labelMode: 'full' },
        lock: true
      }
    },
    focusReviewRange (chart, entryTime, exitTime) {
      const rows = typeof chart.getDataList === 'function' ? chart.getDataList() : []
      const entryIndex = findNearestBarIndex(rows, entryTime)
      const exitIndex = findNearestBarIndex(rows, exitTime)
      if (entryIndex < 0 || exitIndex < 0) return
      const firstIndex = Math.min(entryIndex, exitIndex)
      const lastIndex = Math.max(entryIndex, exitIndex)
      const tradeBars = Math.max(1, lastIndex - firstIndex + 1)
      const visibleBars = Math.min(rows.length, Math.max(48, Math.ceil(tradeBars * 1.2)))
      const size = typeof chart.getSize === 'function' ? chart.getSize() : null
      const chartWidth = size && Number(size.width) > 0 ? Number(size.width) : 1100
      if (typeof chart.setBarSpace === 'function') chart.setBarSpace(Math.max(1, Math.min(18, (chartWidth - 80) / visibleBars)))
      const centerIndex = Math.round((firstIndex + lastIndex) / 2)
      if (typeof chart.scrollToDataIndex === 'function') {
        chart.scrollToDataIndex(centerIndex, 0)
        if (typeof chart.scrollByDistance === 'function') {
          chart.scrollByDistance(-Math.max(0, (chartWidth - 80) / 2), 0)
        }
      } else if (typeof chart.scrollToTimestamp === 'function') {
        chart.scrollToTimestamp(Math.round((entryTime + exitTime) / 2), 0)
      }
    },
    formatDate (value) {
      return formatBacktestTime(value, { locale: this.$i18n.locale, fallback: '-' })
    },
    formatDateRange (assumptions) {
      const start = assumptions && assumptions.startDate
      const end = assumptions && assumptions.endDate
      return start && end ? `${moment(start).format('YYYY-MM-DD')} ~ ${moment(end).format('YYYY-MM-DD')}` : '-'
    },
    formatLeverage (assumptions) {
      const enabled = assumptions && assumptions.leverageEnabled
      const leverage = enabled === false ? 1 : Number((assumptions && assumptions.leverage) || 1)
      return `${Number.isFinite(leverage) ? leverage : 1}×`
    },
    formatStatusReason (value) {
      if (!value) return '-'
      const key = `strategyV2.backtest.statusReasonValue.${value}`
      const translated = this.$t(key)
      return translated === key ? String(value) : translated
    },
    formatPercent (value, signed = true) { const number = Number(value || 0); return `${signed && number > 0 ? '+' : ''}${number.toFixed(2)}%` },
    formatRate (value) { return `${(Number(value || 0) * 100).toFixed(2)}%` },
    formatNumber (value, digits = 2) { const number = Number(value || 0); return Number.isFinite(number) ? number.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '-' },
    formatNullableNumber (value, digits = 2) { return value === null || value === undefined ? '-' : this.formatNumber(value, digits) },
    formatSignedNumber (value, digits = 2) { const number = Number(value || 0); return `${number > 0 ? '+' : ''}${this.formatNumber(number, digits)}` },
    formatWeights (value) { return Object.entries(value || {}).map(([symbol, weight]) => `${symbol.split(':').pop().split('@')[0]} ${this.formatRate(weight)}`).join(' · ') || '-' },
    profitTone (value) { const number = Number(value || 0); return number > 0 ? 'positive' : number < 0 ? 'negative' : 'neutral' },
    signedCell (value) { return this.$createElement('span', { class: this.profitTone(value) }, this.formatSignedNumber(value)) },
    signedPercentCell (value) { return this.$createElement('span', { class: this.profitTone(value) }, this.formatPercent(Number(value || 0) * 100)) },
    statusColor (value) { return { filled: 'green', partial: 'orange', deferred: 'blue', rejected: 'red' }[value] || 'default' }
  }
}
</script>

<style lang="less" scoped>
.portfolio-result { min-width: 0; }
.result-trustbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; padding: 10px 12px; border: 1px solid; border-radius: 8px; }
.result-trustbar > div { display: flex; align-items: center; gap: 8px; }
.result-trustbar span { color: #64748b; font-size: 12px; }
.result-trustbar.is-success { border-color: #b7eb8f; background: #f6ffed; color: #3f8600; }
.result-trustbar.is-warning { border-color: #ffe58f; background: #fffbe6; color: #ad6800; }
.result-trustbar.is-error { border-color: #ffccc7; background: #fff2f0; color: #cf1322; }
.metrics-grid { display: grid; grid-template-columns: repeat(8, minmax(105px, 1fr)); gap: 8px; }
.metric-card, .overview-card, .status-card { min-width: 0; padding: 12px; border: 1px solid #edf0f4; border-radius: 8px; background: #f8fafc; }
.metric-card { display: flex; flex-direction: column; gap: 3px; }
.metric-card span, .overview-card span, .status-card span { color: #7c8ca1; font-size: 11px; }
.metric-label { display: inline-flex; align-items: center; gap: 5px; }
.metric-label .anticon { cursor: help; }
.metric-card strong { color: #20324a; font-size: 18px; font-variant-numeric: tabular-nums; }
.positive { color: #16a34a !important; }
.negative { color: #dc2626 !important; }
.neutral { color: #94a3b8 !important; }
.chart-card { margin-top: 12px; padding: 13px; border: 1px solid #edf0f4; border-radius: 8px; }
.chart-heading { display: flex; justify-content: space-between; gap: 16px; }
.chart-heading h3 { margin: 0; color: #26364c; font-size: 14px; }
.chart-heading span, .chart-legend-note { color: #7c8ca1; font-size: 11px; }
.portfolio-chart { width: 100%; height: 590px; }
.assumption-strip, .overview-grid, .status-grid { display: grid; gap: 8px; margin-top: 12px; }
.assumption-strip { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.assumption-strip div { padding: 9px 10px; border-radius: 8px; background: #f8fafc; }
.assumption-strip span { display: block; color: #7c8ca1; font-size: 11px; }
.assumption-strip strong { display: block; color: #334155; font-size: 11px; }
.overview-grid { grid-template-columns: repeat(4, 1fr); }
.overview-card, .status-card { display: flex; justify-content: space-between; align-items: center; }
.overview-card strong, .status-card strong { font-size: 18px; }
.status-grid { grid-template-columns: repeat(4, 1fr); }
.status-card.status-partial { border-color: rgba(250, 173, 20, .45); }
.status-card.status-deferred { border-color: rgba(24, 144, 255, .45); }
.status-card.status-rejected { border-color: rgba(255, 77, 79, .45); }
.result-tabs { margin-top: 12px; }
.grid-accounting-alert { margin-bottom: 12px; }
.audit-summary { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 12px; border-radius: 8px; }
.audit-summary.passed { color: #52c41a; background: rgba(82, 196, 26, .08); }
.audit-summary.failed { color: #ff4d4f; background: rgba(255, 77, 79, .08); }
.audit-summary div { display: flex; flex-direction: column; }
.audit-summary span { color: #7c8ca1; font-size: 11px; }
.clickable-table /deep/ tbody tr { cursor: pointer; }
.clickable-table /deep/ tbody tr:hover td { background: rgba(82, 196, 26, .08) !important; }
.review-summary { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 10px; border-radius: 8px; background: #f8fafc; }
.review-summary b { margin-left: auto; }
.review-chart-shell { width: 100%; height: 68vh; min-height: 520px; max-height: 680px; overflow: hidden; }
.review-chart-shell /deep/ .chart-left { width: 100% !important; height: 100% !important; }
.review-chart-shell /deep/ .kline-chart-container { height: auto !important; min-height: 0; }
.portfolio-result.theme-dark .metric-card, .portfolio-result.theme-dark .overview-card, .portfolio-result.theme-dark .status-card, .portfolio-result.theme-dark .assumption-strip div { border-color: rgba(255,255,255,.1); background: #0d0d0d; }
.portfolio-result.theme-dark .metric-card strong, .portfolio-result.theme-dark .overview-card strong, .portfolio-result.theme-dark .status-card strong, .portfolio-result.theme-dark .chart-heading h3, .portfolio-result.theme-dark .assumption-strip strong { color: #e5e7eb; }
.liquidation-alert { margin-top: 12px; }
.portfolio-result.theme-dark .chart-card { border-color: rgba(255,255,255,.1); }
.portfolio-result.theme-dark .result-trustbar.is-success { border-color: #315d22; background: #13200f; color: #73d13d; }
.portfolio-result.theme-dark .result-trustbar.is-warning { border-color: #664d03; background: #211b08; color: #ffc53d; }
.portfolio-result.theme-dark .result-trustbar.is-error { border-color: #6b2525; background: #251111; color: #ff7875; }
.portfolio-result.theme-dark .result-trustbar span { color: rgba(255, 255, 255, .56); }
.portfolio-result.theme-dark .result-trustbar /deep/ .trust-tag { font-weight: 500; }
.portfolio-result.theme-dark .result-trustbar /deep/ .trust-tag--success { border-color: #315d22; background: rgba(82, 196, 26, .18); color: #b7eb8f; }
.portfolio-result.theme-dark .result-trustbar /deep/ .trust-tag--error { border-color: #6b2525; background: rgba(255, 77, 79, .18); color: #ffa39e; }
.portfolio-result.theme-dark .result-trustbar /deep/ .trust-tag--info { border-color: #164c7e; background: rgba(24, 144, 255, .18); color: #91d5ff; }
.portfolio-result.theme-dark .result-trustbar /deep/ .trust-tag--warning { border-color: #664d03; background: rgba(250, 173, 20, .18); color: #ffe58f; }
@media (max-width: 1500px) { .metrics-grid { grid-template-columns: repeat(4, 1fr); } }
@media (max-width: 900px) { .metrics-grid, .overview-grid, .status-grid, .assumption-strip { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 720px) { .result-trustbar { align-items: flex-start; flex-direction: column; }.result-trustbar > div { flex-wrap: wrap; } }
</style>

<style lang="less">
body.dark .review-summary { color: rgba(255,255,255,.88); background: #111; }
.trade-review-modal .ant-modal { max-width: calc(100vw - 32px); padding-bottom: 24px; }
.trade-review-modal .ant-modal-body { padding: 16px; }
</style>
