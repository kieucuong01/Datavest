<template>
  <div class="legacy-page" :class="{ 'theme-dark': isDarkTheme }">

    <main class="legacy-main">
      <section class="analysis-controls" :aria-label="$t('smartInsights.analysisControls')">
        <div class="date-control">
          <label>{{ $t('smartInsights.analysisDate') }}</label>
          <a-select
            v-model="asOf"
            allow-clear
            size="small"
            :loading="datesLoading"
            :disabled="datesLoading"
            @change="loadAll">
            <a-select-option v-for="item in dates" :key="item" :value="item">{{ formatDate(item) }}</a-select-option>
          </a-select>
        </div>
        <a-button size="small" @click="showToday">{{ $t('smartInsights.today') }}</a-button>
        <div class="control-spacer" />
      </section>

      <a-alert v-if="errorMessage" class="legacy-alert" type="error" show-icon :message="errorMessage" />

      <section v-if="overviewLoading && !overview" class="initial-overview-loading" aria-busy="true" aria-live="polite">
        <a-skeleton active :paragraph="{ rows: 5 }" />
      </section>
      <template v-else>
        <section class="daily-hero">
          <div class="hero-copy">
            <div class="hero-kicker">
              <span class="hero-badge"><a-icon type="bar-chart" /> {{ $t('smartInsights.legacyHeroBadge') }}</span>
              <span class="hero-status">{{ overviewStatus }}</span>
              <span class="hero-date">{{ analysisDateLabel }}</span>
            </div>
            <h1>{{ $t('smartInsights.legacyHeroTitle') }}</h1>
            <p><span class="hero-arrow">▲</span> {{ dailyBriefSummary }}</p>
            <a-button v-if="dailyBrief.status === 'AVAILABLE'" ghost size="small" class="hero-read-more" @click="heroExpanded = !heroExpanded">
              {{ heroExpanded ? $t('smartInsights.collapse') : $t('smartInsights.readMore') }}
            </a-button>
            <p v-if="heroExpanded && dailyBrief.status === 'AVAILABLE'" class="hero-thesis">{{ dailyBrief.content }}</p>
          </div>
          <button type="button" class="hero-audio" :disabled="dailyBrief.status !== 'AVAILABLE'" @click="toggleHeroSpeech">
            <span class="play-button"><a-icon :type="heroSpeechActive ? 'pause' : 'caret-right'" /></span>
            <span><strong>{{ $t('smartInsights.listenAi') }}</strong><small>{{ heroSpeechActive ? $t('smartInsights.stopListening') : $t('smartInsights.dailyBriefTts') }}</small></span>
          </button>
        </section>

        <section class="legacy-card decision-brief-card" aria-labelledby="decision-brief-title">
          <div class="card-heading">
            <div class="heading-with-icon"><span class="section-icon">✓</span><div><h2 id="decision-brief-title">{{ $t('smartInsights.decisionBrief') }}</h2><p>{{ $t('smartInsights.decisionBriefDesc') }}</p></div></div>
            <a-tag :color="dailyBrief.status === 'UNAVAILABLE' ? 'orange' : 'green'">{{ overviewStatus }}</a-tag>
          </div>
          <div class="brief-facts">
            <div><small>{{ $t('smartInsights.analysisDate') }}</small><strong>{{ analysisDateLabel }}</strong></div>
            <div><small>{{ $t('smartInsights.assets') }}</small><strong>{{ dailyBrief.assetCount || 0 }}</strong></div>
            <div><small>{{ $t('smartInsights.latestAiAnalysis') }}</small><strong>{{ dailyBrief.generatedAt ? formatDateTime(dailyBrief.generatedAt) : $t('smartInsights.notAvailable') }}</strong></div>
            <div><small>{{ $t('smartInsights.checksum') }}</small><code>{{ shortChecksum(dailyBrief.sourceChecksum) }}</code></div>
          </div>
        </section>
      </template>

      <asset-opinions-section
        :rows="opinionRows"
        :loading="opinionsLoading || overviewLoading"
        @refresh="loadAll"
        @open-analysis="openAssetAnalysis"
        @open-ai-assistant="openAiAssistant"
      />

      <economic-calendar-table
        class="crypto-calendar"
        :events="calendarEvents"
        :filter="calendarFilter"
        :loading="calendarLoading"
        :error="calendarError"
        @filter-change="calendarFilter = $event"
      />

      <market-pulse-section
        :pulse="cryptoPulse || {}"
        :overview="overview || {}"
        :calendar-events="calendarEvents"
        :locale="$i18n && $i18n.locale"
        :loading="pulseLoading"
        @open-evidence="openEvidence"
      />
    </main>

    <footer class="legacy-footer">
      <div class="footer-inner"><div><div class="legacy-brand"><span class="brand-mark">D</span><strong>DataVest</strong></div><p>{{ $t('smartInsights.footerDescription') }}</p></div><div><h3>{{ $t('smartInsights.footerProduct') }}</h3><a href="#" @click.prevent>{{ $t('smartInsights.overviewNav') }}</a><a href="#" @click.prevent>{{ $t('smartInsights.portfolioNav') }}</a><a href="#" @click.prevent>{{ $t('smartInsights.quantRoomNav') }}</a><a href="#" @click.prevent>{{ $t('smartInsights.footerMethodology') }}</a></div></div>
      <div class="footer-bottom"><span>{{ $t('smartInsights.footerDisclaimer') }}</span><span>© {{ new Date().getFullYear() }} Datavest.vn.</span></div>
    </footer>

    <a-modal
      :visible="analysisModalVisible"
      :title="analysisModalTitle"
      :width="760"
      centered
      :footer="null"
      :destroy-on-close="false"
      :mask-closable="true"
      :wrap-class-name="isDarkTheme ? 'asset-analysis-modal theme-dark' : 'asset-analysis-modal'"
      @cancel="closeAssetAnalysis"
    >
      <div v-if="selectedOpinionRow" class="asset-analysis-modal-body" :class="{ 'theme-dark': isDarkTheme }">
        <div class="asset-analysis-header">
          <div>
            <strong>{{ selectedOpinionRow.displaySymbol }}</strong>
            <span>{{ marketLabel(selectedOpinionRow.market) }}</span>
          </div>
          <a-tag :color="selectedOpinionReport ? 'green' : 'orange'">
            {{ selectedOpinionReport ? overviewStatus : $t('smartInsights.dataUnavailableShort') }}
          </a-tag>
        </div>

        <div v-if="selectedOpinionReport" class="asset-analysis-meta">
          <span>{{ $t('smartInsights.analysisDate') }}: {{ analysisDateLabel }}</span>
          <span>{{ $t('smartInsights.lastAiRun') }}: {{ formatDateTime(selectedOpinionReport.createdAt) }}</span>
          <span v-if="selectedOpinionDetails.timeframe">{{ $t('smartInsights.timeframe') }}: {{ selectedOpinionDetails.timeframe }}</span>
          <span v-if="selectedOpinionDetails.model">{{ $t('smartInsights.model') }}: {{ selectedOpinionDetails.model }}</span>
        </div>

        <section v-if="selectedOpinionReport" class="analysis-drawer-section">
          <div class="analysis-drawer-section-title"><a-icon type="thunderbolt" /><h3>{{ $t('smartInsights.analysisOverview') }}</h3></div>
          <div class="analysis-result-grid">
            <div><small>{{ $t('smartInsights.aiDecision') }}</small><strong :class="analysisDecisionClass(selectedOpinionReport.decision)">{{ analysisTrendLabel(selectedOpinionReport.decision) }}</strong></div>
            <div><small>{{ $t('smartInsights.aiConfidence') }}</small><strong>{{ selectedOpinionReport.confidence != null ? `${selectedOpinionReport.confidence}%` : $t('smartInsights.notAvailable') }}</strong></div>
          </div>
          <div v-if="selectedOpinionReport.summary" class="analysis-copy">
            <h4>{{ $t('smartInsights.aiSummary') }}</h4>
            <p>{{ selectedOpinionReport.summary }}</p>
          </div>
          <div v-if="selectedMarketMetrics.length" class="analysis-metric-grid">
            <div v-for="metric in selectedMarketMetrics" :key="metric.key" class="analysis-metric-item">
              <small>{{ metric.label }}</small>
              <strong :class="metric.tone">{{ metric.value }}</strong>
            </div>
          </div>
        </section>
        <section v-else class="analysis-drawer-section analysis-empty">
          <a-icon type="clock-circle" />
          <p>{{ $t('smartInsights.aiNoResult') }}</p>
          <router-link to="/ai-asset-analysis" @click.native="closeAssetAnalysis">{{ $t('smartInsights.manageWatchlist') }}</router-link>
        </section>

        <section v-if="selectedOpinionReport" class="analysis-drawer-section">
          <div class="analysis-drawer-section-title"><a-icon type="database" /><h3>{{ $t('smartInsights.analysisInputs') }}</h3></div>
          <p class="analysis-evidence-desc">{{ $t('smartInsights.analysisInputsDesc') }}</p>
          <div v-if="selectedInputRows.length" class="analysis-factor-grid">
            <div v-for="item in selectedInputRows" :key="item.key" class="analysis-factor-item">
              <small>{{ item.label }}</small><strong>{{ item.value }}</strong>
            </div>
          </div>
          <div v-else class="analysis-empty analysis-empty--compact"><span>{{ $t('smartInsights.analysisInputsUnavailable') }}</span></div>
        </section>

        <section v-if="selectedTradingPlanRows.length" class="analysis-drawer-section">
          <div class="analysis-drawer-section-title"><a-icon type="flag" /><h3>{{ $t('smartInsights.tradingPlan') }}</h3></div>
          <p class="analysis-evidence-desc">{{ $t('smartInsights.tradingPlanDesc') }}</p>
          <div class="analysis-factor-grid">
            <div v-for="item in selectedTradingPlanRows" :key="item.key" class="analysis-factor-item">
              <small>{{ item.label }}</small><strong>{{ item.value }}</strong>
            </div>
          </div>
        </section>

        <section v-if="selectedDetailRows.length" class="analysis-drawer-section">
          <div class="analysis-drawer-section-title"><a-icon type="file-text" /><h3>{{ $t('smartInsights.analysisDetails') }}</h3></div>
          <div class="analysis-detail-list">
            <article v-for="item in selectedDetailRows" :key="item.key" class="analysis-detail-item">
              <div class="analysis-detail-item-title"><a-icon :type="item.icon" /><strong>{{ item.title }}</strong></div>
              <p>{{ item.text }}</p>
            </article>
          </div>
        </section>

        <section v-if="selectedCryptoFactorRows.length || selectedOpinionDetails.cryptoFactorBreakdown.length" class="analysis-drawer-section">
          <div class="analysis-drawer-section-title"><a-icon type="fund" /><h3>{{ $t('smartInsights.cryptoFactors') }}</h3></div>
          <p v-if="selectedOpinionDetails.cryptoFactorSummary" class="analysis-evidence-desc">{{ selectedOpinionDetails.cryptoFactorSummary }}</p>
          <div v-if="selectedCryptoFactorRows.length" class="analysis-factor-grid">
            <div v-for="factor in selectedCryptoFactorRows" :key="factor.key" class="analysis-factor-item">
              <small>{{ factor.label }}</small><strong>{{ factor.value }}</strong>
            </div>
          </div>
          <ul v-if="selectedOpinionDetails.cryptoFactorBreakdown.length" class="analysis-bullet-list">
            <li v-for="(factor, index) in selectedOpinionDetails.cryptoFactorBreakdown" :key="`factor-${index}`">
              <strong>{{ factor.factor || $t('smartInsights.factor') }}</strong><span>{{ factor.reason || factor.score }}</span>
            </li>
          </ul>
        </section>

        <section v-if="selectedIndicatorRows.length" class="analysis-drawer-section">
          <div class="analysis-drawer-section-title"><a-icon type="stock" /><h3>{{ $t('smartInsights.indicators') }}</h3></div>
          <div class="analysis-factor-grid">
            <div v-for="indicator in selectedIndicatorRows" :key="indicator.key" class="analysis-factor-item">
              <small>{{ indicator.label }}</small><strong>{{ indicator.value }}</strong><span v-if="indicator.hint">{{ indicator.hint }}</span>
            </div>
          </div>
        </section>

        <section v-if="selectedTrendRows.length || selectedOpinionDetails.trendOutlookSummary || selectedConsensusRows.length" class="analysis-drawer-section">
          <div class="analysis-drawer-section-title"><a-icon type="cluster" /><h3>{{ $t('smartInsights.consensusAndOutlook') }}</h3></div>
          <p v-if="selectedOpinionDetails.trendOutlookSummary" class="analysis-evidence-desc">{{ selectedOpinionDetails.trendOutlookSummary }}</p>
          <div v-if="selectedConsensusRows.length" class="analysis-consensus-grid">
            <div v-for="item in selectedConsensusRows" :key="item.key"><small>{{ item.label }}</small><strong :class="item.key === 'decision' ? analysisDecisionClass(item.value) : ''">{{ item.key === 'decision' ? analysisTrendLabel(item.value) : item.value }}</strong></div>
          </div>
          <div v-if="selectedTrendRows.length" class="analysis-trend-list">
            <div v-for="trend in selectedTrendRows" :key="trend.key" class="analysis-trend-item">
              <span>{{ trend.label }}</span><strong :class="analysisDecisionClass(trend.trend)">{{ analysisTrendLabel(trend.trend) }}</strong><small>{{ trend.score != null ? trend.score : '—' }} · {{ trend.strength || '—' }}</small>
            </div>
          </div>
        </section>

        <section class="analysis-drawer-section analysis-evidence">
          <div class="analysis-drawer-section-title"><a-icon type="bulb" /><h3>{{ $t('smartInsights.analysisArguments') }}</h3></div>
          <p class="analysis-evidence-desc">{{ $t('smartInsights.analysisArgumentsDesc') }}</p>
          <div v-if="selectedOpinionReport && selectedOpinionReport.reasons && selectedOpinionReport.reasons.length" class="analysis-evidence-list">
            <article v-for="(reason, index) in selectedOpinionReport.reasons" :key="index" class="analysis-evidence-item">
              <div class="analysis-evidence-item-head">
                <strong>{{ selectedOpinionRow.displaySymbol }}</strong>
                <span>{{ analysisDateLabel }}</span>
              </div>
              <div class="analysis-evidence-item-meta">
                <span>{{ $t('smartInsights.lastAiRun') }}: {{ formatDateTime(selectedOpinionReport.createdAt) }}</span>
                <span>{{ $t('smartInsights.aiConfidence') }}: {{ selectedOpinionReport.confidence != null ? `${selectedOpinionReport.confidence}%` : $t('smartInsights.notAvailable') }}</span>
              </div>
              <p class="analysis-evidence-item-copy">{{ reason }}</p>
            </article>
          </div>
          <div v-else class="analysis-empty analysis-empty--compact">
            <span>{{ $t('smartInsights.aiReportUnavailable') }}</span>
          </div>
          <div v-if="selectedOpinionDetails.risks.length" class="analysis-risks">
            <h4>{{ $t('smartInsights.risks') }}</h4>
            <ul class="analysis-bullet-list"><li v-for="(risk, index) in selectedOpinionDetails.risks" :key="`risk-${index}`">{{ risk }}</li></ul>
          </div>
        </section>
      </div>
    </a-modal>

    <a-drawer
      :visible="evidenceVisible"
      :title="$t('smartInsights.evidence')"
      :width="560"
      :wrap-class-name="isDarkTheme ? 'insights-drawer theme-dark' : 'insights-drawer'"
      @close="evidenceVisible = false"
    >
      <a-spin :spinning="evidenceLoading"><a-descriptions v-if="evidence" bordered :column="1" size="small"><a-descriptions-item :label="$t('smartInsights.provider')">{{ evidence.sourceName || evidence.source }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.sourceUrl')"><a v-if="evidence.sourceUrl" :href="evidence.sourceUrl" target="_blank" rel="noopener">{{ evidence.sourceUrl }}</a><span v-else>—</span></a-descriptions-item><a-descriptions-item :label="$t('smartInsights.observedAt')">{{ evidence.observedAt }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.effectiveAt')">{{ evidence.effectiveAt }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.reliability')">{{ evidence.reliability || '—' }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.dataClass')">{{ evidence.dataClass || '—' }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.methodology')">{{ evidence.methodologyVersion }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.value')"><pre>{{ pretty(evidence.value) }}</pre></a-descriptions-item><a-descriptions-item :label="$t('smartInsights.warnings')">{{ (evidence.warnings || []).join(', ') || $t('smartInsights.none') }}</a-descriptions-item><a-descriptions-item :label="$t('smartInsights.checksum')"><code>{{ evidence.checksum }}</code></a-descriptions-item></a-descriptions></a-spin>
    </a-drawer>
    <a-drawer
      :visible="healthVisible"
      :title="$t('smartInsights.dataHealth')"
      :width="760"
      :wrap-class-name="isDarkTheme ? 'insights-drawer theme-dark' : 'insights-drawer'"
      @close="healthVisible = false"
    >
      <a-spin :spinning="healthLoading">
        <a-table
          row-key="code"
          size="small"
          :pagination="false"
          :columns="healthColumns"
          :data-source="health"
          :scroll="{ x: 700 }"
        />
      </a-spin>
    </a-drawer>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import { getWatchlist } from '@/api/market'
import { getEconomicCalendar } from '@/api/global-market'
import { getSmartInsightsCryptoPulse, getSmartInsightsDataHealth, getSmartInsightsDates, getSmartInsightsEvidence, getSmartInsightsOverview } from '@/api/smart-insights'
import { runSectionLoaders } from './loadingCoordinator'
import { buildAssetAnalysisDetails, canShowTradingPlan } from './analysisReport'
import { formatVietnamDate, formatVietnamDateTime } from '@/utils/vietnamTime'
import { buildWatchlistOpinionRows } from './watchlistOpinions'
import AssetOpinionsSection from './components/AssetOpinionsSection'
import EconomicCalendarTable from './components/EconomicCalendarTable'
import MarketPulseSection from './components/MarketPulseSection'

export default {
  name: 'SmartInsights',
  components: { AssetOpinionsSection, EconomicCalendarTable, MarketPulseSection },
  data () {
    return {
      asOf: undefined,
      dates: [],
      overview: null,
      cryptoPulse: null,
      calendarEvents: [],
      calendarFilter: {
        timePreset: 'thisWeek',
        countries: ['US', 'VN'],
        impacts: [],
        customStart: '',
        customEnd: ''
      },
      calendarLoading: false,
      calendarError: '',
      health: [],
      watchlist: [],
      evidence: null,
      selectedOpinionRow: null,
      datesLoading: false,
      overviewLoading: false,
      opinionsLoading: false,
      pulseLoading: false,
      healthLoading: false,
      evidenceLoading: false,
      evidenceVisible: false,
      analysisModalVisible: false,
      healthVisible: false,
      heroExpanded: false,
      heroSpeechActive: false,
      errorMessage: ''
    }
  },
  computed: {
    ...mapState({ navTheme: state => state.app.theme }),
    isDarkTheme () { return this.navTheme === 'dark' || this.navTheme === 'realdark' },
    hasOverview () { return Boolean(this.overview && this.overview.status !== 'UNAVAILABLE') },
    dailyBrief () { return (this.overview && this.overview.dailyBrief) || { status: 'UNAVAILABLE', content: '', assetCount: 0 } },
    opinionRows () {
      return buildWatchlistOpinionRows(this.watchlist, this.overview && this.overview.opinions)
    },
    analysisModalTitle () {
      const symbol = this.selectedOpinionRow && this.selectedOpinionRow.displaySymbol
      return symbol ? `${this.$t('smartInsights.viewAnalysis')} · ${symbol}` : this.$t('smartInsights.viewAnalysis')
    },
    selectedOpinionReport () { return this.selectedOpinionRow && this.selectedOpinionRow.report },
    selectedOpinionDetails () { return buildAssetAnalysisDetails(this.selectedOpinionReport) },
    selectedDetailRows () {
      const details = this.selectedOpinionDetails.detailedAnalysis
      return [
        { key: 'technical', title: this.$t('smartInsights.technicalAnalysis'), icon: 'line-chart', text: details.technical },
        { key: 'fundamental', title: this.$t('smartInsights.fundamentalAnalysis'), icon: 'bank', text: details.fundamental },
        { key: 'sentiment', title: this.$t('smartInsights.sentimentAnalysis'), icon: 'heart', text: details.sentiment }
      ].filter(item => item.text)
    },
    selectedMarketMetrics () {
      const data = this.selectedOpinionDetails.marketData
      const rows = [
        { key: 'current_price', label: this.$t('smartInsights.currentPrice'), value: this.formatAnalysisNumber(data.current_price) },
        { key: 'change_24h', label: this.$t('smartInsights.change24h'), value: this.formatAnalysisPercent(data.change_24h), tone: Number(data.change_24h) < 0 ? 'negative' : 'positive' },
        { key: 'support', label: this.$t('smartInsights.support'), value: this.formatAnalysisNumber(data.support) },
        { key: 'resistance', label: this.$t('smartInsights.resistance'), value: this.formatAnalysisNumber(data.resistance) }
      ]
      return rows.filter(row => row.value !== '—')
    },
    selectedInputRows () {
      const input = this.selectedOpinionDetails.inputData
      const rows = [
        { key: 'capturedAt', label: this.$t('smartInsights.inputCapturedAt'), value: input.capturedAt ? this.formatDateTime(input.capturedAt) : '—' },
        { key: 'priceSource', label: this.$t('smartInsights.priceSource'), value: input.priceSource || '—' },
        { key: 'timeframe', label: this.$t('smartInsights.timeframe'), value: input.timeframe || '—' },
        { key: 'klineAt', label: this.$t('smartInsights.klineAsOf'), value: input.klineAt ? this.formatDateTime(input.klineAt) : '—' },
        { key: 'components', label: this.$t('smartInsights.inputComponents'), value: input.components.length ? input.components.map(value => this.inputComponentLabel(value)).join(', ') : '—' },
        { key: 'checksum', label: this.$t('smartInsights.checksum'), value: input.checksum || '—' }
      ]
      return rows.filter(row => row.value !== '—')
    },
    selectedTradingPlanRows () {
      if (!canShowTradingPlan(this.selectedOpinionReport)) return []
      const plan = this.selectedOpinionDetails.tradingPlan
      const entry = plan.entry_price != null ? plan.entry_price : plan.entryPrice
      const stop = plan.stop_loss != null ? plan.stop_loss : plan.stopLoss
      const target = plan.take_profit != null ? plan.take_profit : plan.takeProfit
      const size = plan.position_size_pct != null ? plan.position_size_pct : plan.positionSizePct
      const rows = [
        { key: 'entry', label: this.$t('smartInsights.entryPrice'), value: this.formatAnalysisNumber(entry) },
        { key: 'stop', label: this.$t('smartInsights.stopLoss'), value: this.formatAnalysisNumber(stop) },
        { key: 'target', label: this.$t('smartInsights.takeProfit'), value: this.formatAnalysisNumber(target) },
        { key: 'size', label: this.$t('smartInsights.positionSize'), value: size != null && size !== '' ? `${this.formatAnalysisNumber(size)}%` : '—' }
      ]
      return rows.filter(row => row.value !== '—')
    },
    selectedIndicatorRows () {
      const indicators = this.selectedOpinionDetails.indicators
      const rows = []
      const add = (key, label, value, hint = '') => {
        if (value !== undefined && value !== null && value !== '') rows.push({ key, label, value, hint })
      }
      if (indicators.rsi) add('rsi', 'RSI (14)', this.formatAnalysisNumber(indicators.rsi.value), indicators.rsi.signal)
      if (indicators.macd) add('macd', 'MACD', indicators.macd.signal || indicators.macd.trend, indicators.macd.trend)
      if (indicators.moving_averages) add('moving_averages', this.$t('smartInsights.movingAverageTrend'), indicators.moving_averages.trend)
      if (indicators.volatility) {
        const volatility = indicators.volatility
        const value = volatility.atr != null ? this.formatAnalysisNumber(volatility.atr) : this.formatAnalysisPercent(volatility.pct)
        add('volatility', this.$t('smartInsights.volatility'), value, volatility.level)
      }
      if (indicators.volume_ratio != null) add('volume_ratio', this.$t('smartInsights.volumeRatio'), `${this.formatAnalysisNumber(indicators.volume_ratio)}×`)
      if (indicators.price_position != null) add('price_position', this.$t('smartInsights.pricePosition'), this.formatAnalysisPercent(indicators.price_position))
      if (indicators.levels) {
        add('support', this.$t('smartInsights.support'), this.formatAnalysisNumber(indicators.levels.support))
        add('resistance', this.$t('smartInsights.resistance'), this.formatAnalysisNumber(indicators.levels.resistance))
      }
      return rows.filter(row => row.value !== '—')
    },
    selectedCryptoFactorRows () {
      const factors = this.selectedOpinionDetails.cryptoFactors
      const definitions = [
        ['volume_24h', this.$t('smartInsights.volume24h'), 'number'],
        ['volume_change_24h', this.$t('smartInsights.volumeChange24h'), 'percent'],
        ['funding_rate', this.$t('smartInsights.fundingRate'), 'percent'],
        ['open_interest', this.$t('smartInsights.openInterest'), 'number'],
        ['open_interest_change_24h', this.$t('smartInsights.openInterestChange24h'), 'percent'],
        ['long_short_ratio', this.$t('smartInsights.longShortRatio'), 'number'],
        ['exchange_netflow', this.$t('smartInsights.exchangeNetflow'), 'number'],
        ['stablecoin_netflow', this.$t('smartInsights.stablecoinNetflow'), 'number']
      ]
      return definitions.map(([key, label, type]) => ({
        key,
        label,
        value: type === 'percent' ? this.formatAnalysisPercent(factors[key]) : this.formatAnalysisNumber(factors[key])
      })).filter(row => row.value !== '—')
    },
    selectedTrendRows () {
      const outlook = this.selectedOpinionDetails.trendOutlook
      return [
        ['next_24h', this.$t('smartInsights.outlook24h')],
        ['next_3d', this.$t('smartInsights.outlook3d')],
        ['next_1w', this.$t('smartInsights.outlook1w')],
        ['next_1m', this.$t('smartInsights.outlook1m')]
      ].map(([key, label]) => {
        const item = outlook[key]
        if (!item || typeof item !== 'object') return null
        return { key, label, trend: item.trend, score: item.score, strength: item.strength }
      }).filter(Boolean)
    },
    selectedConsensusRows () {
      const consensus = this.selectedOpinionDetails.consensus
      return [
        { key: 'decision', label: this.$t('smartInsights.consensusDecision'), value: consensus.consensus_decision },
        { key: 'score', label: this.$t('smartInsights.consensusScore'), value: this.formatAnalysisNumber(consensus.consensus_score) },
        { key: 'agreement', label: this.$t('smartInsights.consensusAgreement'), value: consensus.agreement_ratio != null ? this.formatAnalysisPercent(Number(consensus.agreement_ratio) * 100) : '—' },
        { key: 'regime', label: this.$t('smartInsights.marketRegime'), value: consensus.market_regime }
      ].filter(row => row.value !== undefined && row.value !== null && row.value !== '' && row.value !== '—')
    },
    overviewStatus () { return this.statusLabel(this.hasOverview ? this.overview.status : 'UNAVAILABLE') },
    analysisDateLabel () { return this.formatDate(this.asOf || (this.overview && this.overview.asOf) || this.dates[0]) },
    dailyBriefSummary () { return this.dailyBrief.status === 'AVAILABLE' ? this.dailyBrief.content.split('\n')[0] : this.dailyBrief.content || this.$t('smartInsights.aiNoResult') },
    healthColumns () {
      return [
        { title: this.$t('smartInsights.provider'), dataIndex: 'name', width: 180 },
        { title: this.$t('smartInsights.activationMode'), dataIndex: 'activationMode', customRender: value => this.modeLabel(value), width: 130 },
        { title: this.$t('smartInsights.freshness'), dataIndex: 'freshness', customRender: value => this.stateLabel(value), width: 110 },
        { title: this.$t('smartInsights.coverage'), dataIndex: 'coverage.liveObservations30d', width: 150 },
        { title: this.$t('smartInsights.lastRun'), dataIndex: 'lastRun.status', customRender: value => this.lastRunLabel(value), width: 130 },
        { title: this.$t('smartInsights.methodology'), dataIndex: 'methodologyVersion', width: 150 }
      ]
    }
  },
  mounted () {
    this.loadAll()
  },
  methods: {
    async loadAll () {
      this.errorMessage = ''
      const results = await runSectionLoaders({
        dates: this.loadDates,
        overview: this.loadOverview,
        opinions: this.loadWatchlist,
        pulse: this.loadPulse,
        calendar: this.loadCalendar
      }, this.setSectionLoading)
      const failed = results.find(result => result.status === 'rejected')
      if (failed) {
        this.errorMessage = this.friendlyError(failed.reason, 'smartInsights.unavailable')
      }
    },
    async showToday () {
      this.asOf = new Date().toISOString().slice(0, 10)
      await this.loadAll()
    },
    setSectionLoading (section, active) {
      const fields = { dates: 'datesLoading', overview: 'overviewLoading', opinions: 'opinionsLoading', pulse: 'pulseLoading', calendar: 'calendarLoading' }
      if (fields[section]) this[fields[section]] = active
    },
    async loadOverview () {
      const response = await getSmartInsightsOverview({
        as_of: this.asOf,
        lang: (this.$i18n && this.$i18n.locale) || 'en-US'
      })
      this.overview = response.data
    },
    async loadDates () {
      const response = await getSmartInsightsDates()
      this.dates = (response.data && response.data.dates) || []
      if (!this.asOf && this.dates.length) this.asOf = this.dates[0]
    },
    async loadHealth () {
      this.healthLoading = true
      try { const response = await getSmartInsightsDataHealth(); this.health = (response.data && response.data.sources) || [] } finally { this.healthLoading = false }
    },
    async loadPulse () { const response = await getSmartInsightsCryptoPulse({ as_of: this.asOf, compact: 1 }); this.cryptoPulse = response.data },
    async loadCalendar (force = false) {
      this.calendarLoading = true
      this.calendarError = ''
      try {
        const response = await getEconomicCalendar({ force: force ? 1 : undefined, days: 14, lang: (this.$i18n && this.$i18n.locale) || 'en-US' })
        if (!response || response.code !== 1) throw new Error(response && response.msg ? response.msg : this.$t('smartInsights.calendarUnavailable'))
        this.calendarEvents = Array.isArray(response.data) ? response.data : []
        if (!this.calendarEvents.length && response.meta && response.meta.message) this.calendarError = response.meta.message
      } catch (error) {
        this.calendarEvents = []
        this.calendarError = this.friendlyError(error, 'smartInsights.calendarLoadFailed')
      } finally {
        this.calendarLoading = false
      }
    },
    async loadWatchlist () {
      try {
        const response = await getWatchlist()
        const data = response && response.data
        this.watchlist = Array.isArray(data) ? data : ((data && Array.isArray(data.watchlist)) ? data.watchlist : [])
      } catch (error) {
        this.watchlist = []
        this.errorMessage = this.friendlyError(error, 'smartInsights.watchlistUnavailable')
      }
    },
    async openAssetAnalysis (row) {
      this.selectedOpinionRow = row
      this.analysisModalVisible = true
    },
    openAiAssistant (row) {
      this.$router.push({ path: '/ai-asset-analysis', query: { market: row.market, symbol: row.displaySymbol, action: 'analyze' } })
    },
    closeAssetAnalysis () {
      this.analysisModalVisible = false
    },
    toggleHeroSpeech () {
      if (!this.dailyBrief.content || typeof window === 'undefined' || !window.speechSynthesis) return
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel()
        this.heroSpeechActive = false
        return
      }
      const utterance = new window.SpeechSynthesisUtterance(this.dailyBrief.content)
      utterance.lang = this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US'
      utterance.onend = () => { this.heroSpeechActive = false }
      utterance.onerror = () => { this.heroSpeechActive = false }
      this.heroSpeechActive = true
      window.speechSynthesis.speak(utterance)
    },
    async openEvidence (id) {
      this.evidenceVisible = true; this.evidenceLoading = true; this.evidence = null
      try { const response = await getSmartInsightsEvidence(id); this.evidence = response.data } catch (error) { this.errorMessage = this.friendlyError(error, 'smartInsights.unavailable') } finally { this.evidenceLoading = false }
    },
    statusLabel (status) {
      const labels = {
        COMPLETE: this.$t('smartInsights.availableStatus'),
        AVAILABLE: this.$t('smartInsights.availableStatus'),
        PARTIAL: this.$t('smartInsights.partialStatus'),
        LIVE: this.$t('smartInsights.live'),
        STALE: this.$t('smartInsights.stale'),
        UNAVAILABLE: this.$t('smartInsights.unavailableShort'),
        NEVER: this.$t('smartInsights.never')
      }
      return labels[String(status || 'UNAVAILABLE').toUpperCase()] || this.$t('smartInsights.unavailableShort')
    },
    modeLabel (value) { return this.statusLabel(value) },
    stateLabel (value) { return this.statusLabel(value) },
    lastRunLabel (value) { return this.statusLabel(value || 'NE' + 'VER') },
    severityLabel (value) {
      const labels = { high: this.$t('smartInsights.high'), medium: this.$t('smartInsights.medium'), low: this.$t('smartInsights.low'), danger: this.$t('smartInsights.high'), warning: this.$t('smartInsights.medium') }
      return labels[String(value || '').toLowerCase()] || String(value || this.$t('smartInsights.notAvailable'))
    },
    impactLabel (value) {
      const labels = { high: this.$t('smartInsights.high'), medium: this.$t('smartInsights.medium'), low: this.$t('smartInsights.low') }
      return labels[String(value || '').toLowerCase()] || value || this.$t('smartInsights.notAvailable')
    },
    formatAnalysisNumber (value) {
      if (value === undefined || value === null || value === '') return '—'
      const number = Number(value)
      if (!Number.isFinite(number)) return String(value)
      return number.toLocaleString(this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US', { maximumFractionDigits: 4 })
    },
    formatAnalysisPercent (value) {
      if (value === undefined || value === null || value === '') return '—'
      const number = Number(value)
      return Number.isFinite(number) ? `${number > 0 ? '+' : ''}${number.toFixed(2)}%` : String(value)
    },
    inputComponentLabel (value) {
      const labels = {
        price: 'inputComponentPrice',
        technical: 'inputComponentTechnical',
        macro: 'inputComponentMacro',
        news: 'inputComponentNews',
        crypto_market_structure: 'inputComponentCryptoStructure'
      }
      return this.$t(`smartInsights.${labels[value] || 'inputComponents'}`)
    },
    analysisDecisionClass (value) {
      const normalized = String(value || '').toUpperCase()
      return normalized === 'BUY' ? 'analysis-positive' : normalized === 'SELL' ? 'analysis-negative' : 'analysis-neutral'
    },
    analysisTrendLabel (value) {
      const normalized = String(value || '').toUpperCase()
      if (normalized === 'BUY') return this.$t('smartInsights.buy')
      if (normalized === 'SELL') return this.$t('smartInsights.sell')
      if (normalized === 'HOLD') return this.$t('smartInsights.neutral')
      return value || this.$t('smartInsights.notAvailable')
    },
    friendlyError (error, key) {
      if (this.$i18n && this.$i18n.locale === 'vi-VN') return this.$t(key)
      return String((error && error.message) || this.$t(key))
    },
    pretty (value) { return JSON.stringify(value || {}, null, 2) },
    shortChecksum (value) { const text = String(value || ''); return text ? `${text.slice(0, 10)}...${text.slice(-6)}` : this.$t('smartInsights.notAvailable') },
    formatDate (value) { return formatVietnamDate(value, { locale: this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-GB', fallback: this.$t('smartInsights.dataUnavailableShort') }) },
    formatDateTime (value) {
      if (!value) return this.$t('smartInsights.notAvailable')
      const locale = this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-GB'
      return formatVietnamDateTime(value, { locale, fallback: String(value) })
    },
    marketLabel (value) { const labels = { all: this.$t('smartInsights.all'), crypto: 'Crypto', vn: 'VN', us: 'US', gold: this.$t('smartInsights.gold') }; return labels[value] || String(value || '').toUpperCase() }
  }
}
</script>

<style lang="less" scoped>
.asset-analysis-modal-body { --page-bg: #f7f9fc; --ink: #17253d; --muted: #7b8798; --line: #e4eaf3; --card: #fff; --blue: var(--primary-color, #174ca8); --soft-blue: var(--primary-color-soft, rgba(24,144,255,.1)); max-height: 72vh; padding-right: 4px; overflow-y: auto; color: var(--ink); }
.asset-analysis-modal-body.theme-dark { --page-bg: #111827; --ink: #eef4ff; --muted: #9aa8bc; --line: #2a3547; --card: #182235; --soft-blue: rgba(24,144,255,.16); }
.asset-analysis-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }.asset-analysis-header > div { display: grid; gap: 3px; }.asset-analysis-header strong { color: var(--ink); font-size: 18px; }.asset-analysis-header span { color: var(--muted); font-size: 12px; }
.asset-analysis-meta { display: flex; flex-wrap: wrap; gap: 12px; padding: 10px 0; color: var(--muted); font-size: 12px; }
.analysis-drawer-section { margin-top: 16px; padding: 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--card); }.analysis-drawer-section-title { display: flex; align-items: center; gap: 7px; }.analysis-drawer-section-title .anticon { color: var(--blue); }.analysis-drawer-section-title h3 { margin: 0; color: var(--ink); font-size: 15px; }.analysis-result-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }.analysis-result-grid > div { display: grid; gap: 4px; padding: 9px 10px; border-radius: 8px; background: var(--soft-blue); }.analysis-result-grid small { color: var(--muted); font-size: 11px; }.analysis-result-grid strong { color: var(--ink); font-size: 16px; }.analysis-copy { margin-top: 13px; }.analysis-copy h4 { margin: 0 0 5px; color: var(--ink); font-size: 13px; }.analysis-copy p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.65; white-space: pre-wrap; }.analysis-report { margin-top: 13px; overflow: auto; color: var(--ink); font-size: 13px; line-height: 1.6; }.analysis-report :deep(.qd-report) { max-width: 100%; }
.analysis-evidence-desc { margin: 5px 0 10px; color: var(--muted); font-size: 12px; }.analysis-evidence-list { display: grid; gap: 8px; }.analysis-evidence-item { padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--page-bg); }.analysis-evidence-item-head, .analysis-evidence-item-meta { display: flex; justify-content: space-between; gap: 10px; }.analysis-evidence-item-head strong { color: var(--ink); font-size: 13px; }.analysis-evidence-item-head span, .analysis-evidence-item-meta { color: var(--muted); font-size: 11px; }.analysis-evidence-item-meta { margin-top: 4px; flex-wrap: wrap; }.analysis-evidence-item-copy { margin: 8px 0 0; color: var(--ink); font-size: 13px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }.analysis-evidence-item a { display: block; overflow: hidden; margin-top: 7px; color: var(--blue); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }.analysis-evidence-item pre { max-height: 150px; margin: 8px 0 0; padding: 8px; overflow: auto; border-radius: 6px; color: var(--ink); background: var(--card); font-size: 11px; white-space: pre-wrap; word-break: break-word; }.analysis-empty { display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 7px; min-height: 90px; color: var(--muted); text-align: center; }.analysis-empty p { margin: 0; font-size: 13px; }.analysis-empty a { color: var(--blue); font-size: 13px; }.analysis-empty--compact { min-height: 48px; }
.legacy-page { --page-bg: #f7f9fc; --ink: #17253d; --muted: #7b8798; --line: #e4eaf3; --card: #fff; --blue: var(--primary-color, #174ca8); --blue-hover: var(--primary-color-hover, #40a9ff); --blue-active: var(--primary-color-active, #096dd9); --blue-ring: var(--primary-color-ring, rgba(24,144,255,.22)); --soft-blue: var(--primary-color-soft, rgba(24,144,255,.1)); --soft-blue-strong: var(--primary-color-soft-strong, rgba(24,144,255,.18)); position: relative; min-height: calc(100vh - 64px); overflow: hidden; color: var(--ink); background: var(--page-bg); font-size: 15px; }
.legacy-main, .footer-inner, .footer-bottom { width: 100%; max-width: 1120px; margin: 0 auto; }
.legacy-main { width: 100%; max-width: 1480px; margin: 0 auto; box-sizing: border-box; padding: 24px 28px 48px; }.analysis-controls { display: flex; align-items: end; gap: 10px; min-height: 40px; margin-bottom: 17px; }.date-control { display: grid; grid-template-columns: auto 130px; align-items: center; gap: 8px; }.date-control label { color: var(--muted); font-size: 13px; font-weight: 600; }.date-control .ant-select { width: 130px; }.analysis-controls .ant-btn, .analysis-controls .ant-radio-button-wrapper, .date-control .ant-select-selection-selected-value { font-size: 13px; }.control-spacer { flex: 1; }.legacy-alert { margin-bottom: 12px; }.initial-overview-loading { min-height: 184px; padding: 34px 38px; border: 1px solid var(--line); border-radius: 17px; background: var(--card); box-shadow: 0 8px 24px var(--blue-ring); }
.daily-hero { display: flex; align-items: center; justify-content: space-between; min-height: 184px; padding: 30px 38px; overflow: hidden; border-radius: 17px; color: #fff; background: linear-gradient(115deg, var(--blue-active) 0%, var(--blue) 52%, var(--blue-hover) 122%); box-shadow: 0 14px 28px var(--blue-ring); }.hero-copy { position: relative; z-index: 1; min-width: 0; }.hero-kicker { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; color: rgba(255,255,255,.78); font-size: 12px; }.hero-badge, .hero-status { padding: 4px 9px; border: 1px solid rgba(255,255,255,.2); border-radius: 999px; background: rgba(255,255,255,.12); }.hero-badge { font-weight: 700; }.daily-hero h1 { max-width: 620px; margin: 0 0 9px; color: #fff; font-size: clamp(30px, 4vw, 42px); line-height: 1.08; letter-spacing: -.04em; }.daily-hero p { margin: 0; color: rgba(255,255,255,.82); font-size: 13px; }.hero-thesis { margin-top: 6px !important; color: rgba(255,255,255,.62) !important; }.hero-arrow { color: var(--blue-hover); }.hero-audio { display: flex; align-items: center; gap: 12px; min-width: 190px; padding: 11px 15px; border: 1px solid rgba(255,255,255,.18); border-radius: 12px; color: #fff; text-align: left; background: rgba(255,255,255,.1); opacity: .7; }.hero-audio strong, .hero-audio small { display: block; }.hero-audio strong { font-size: 13px; }.hero-audio small { margin-top: 3px; color: rgba(255,255,255,.62); font-size: 11px; }.play-button { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%; color: var(--blue); background: rgba(255,255,255,.75); }
.legacy-card { margin-top: 16px; overflow: hidden; border: 1px solid var(--line); border-radius: 12px; background: var(--card); box-shadow: 0 3px 12px var(--blue-ring); }.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 17px; border-bottom: 1px solid var(--line); background: linear-gradient(var(--soft-blue), var(--card)); }.heading-with-icon { display: flex; align-items: flex-start; gap: 9px; min-width: 0; }.section-icon { display: inline-grid; place-items: center; flex: 0 0 auto; width: 30px; height: 30px; border-radius: 8px; color: #fff; background: var(--blue); font-size: 17px; font-weight: 700; }.card-heading h2 { margin: 0; color: var(--ink); font-size: 16px; line-height: 1.3; }.card-heading p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }.card-heading h2 .ant-tag { vertical-align: 2px; color: #18a575; border-color: #b7ead6; background: #ecfbf4; }
.change-list { width: 100%; }.change-row { display: grid; grid-template-columns: 1.1fr 1fr 20px; align-items: center; gap: 12px; min-height: 52px; padding: 10px 16px; border-bottom: 1px solid var(--line); }.change-row:last-child { border-bottom: 0; }.change-row > div:first-child { display: grid; gap: 2px; }.change-row strong { font-size: 13px; }.change-row span, .change-row small { color: var(--muted); font-size: 12px; }.change-detail { display: flex; justify-content: space-between; gap: 10px; }.legacy-empty { display: flex; align-items: center; justify-content: center; gap: 9px; color: var(--muted); text-align: center; }.legacy-empty div { display: grid; gap: 4px; text-align: left; }.legacy-empty span, .legacy-empty strong { font-size: 13px; }.calendar-empty { min-height: 120px; flex-direction: column; }
.brief-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; padding: 1px; background: var(--line); }.brief-facts > div { display: grid; gap: 5px; min-height: 72px; padding: 14px 16px; background: var(--card); }.brief-facts small { color: var(--muted); font-size: 11px; }.brief-facts strong, .brief-facts code { color: var(--ink); font-size: 14px; font-variant-numeric: tabular-nums; }.brief-facts code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.risk-alerts { display: grid; gap: 8px; margin-top: 12px; }.risk-alerts .ant-alert { border-radius: 9px; }.crypto-calendar { margin-top: 18px; }.calendar-filters { display: flex; gap: 4px; }.calendar-filters .ant-btn { padding: 0 9px; font-size: 12px; }
.legacy-footer { margin-top: 22px; border-top: 1px solid var(--line); background: var(--card); }.footer-inner { display: grid; grid-template-columns: 1.5fr 1fr; gap: 24px; padding: 36px 0 30px; }.legacy-brand { display: inline-flex; align-items: center; gap: 6px; color: var(--ink); white-space: nowrap; }.brand-mark { display: inline-grid; place-items: center; width: 25px; height: 25px; border-radius: 6px; color: #fff; background: var(--blue); font-size: 14px; font-weight: 800; }.footer-inner p { max-width: 320px; margin: 10px 0 0; color: var(--muted); font-size: 12px; line-height: 1.7; }.footer-inner > div:last-child { display: grid; align-content: start; gap: 6px; justify-self: end; min-width: 150px; }.footer-inner h3 { margin: 0 0 3px; color: var(--muted); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }.footer-inner a { color: var(--muted); font-size: 12px; text-decoration: none; }.footer-bottom { display: flex; justify-content: space-between; gap: 16px; padding: 12px 0; border-top: 1px solid var(--line); color: var(--muted); font-size: 11px; }.footer-bottom span:first-child { max-width: 720px; }.demo-watermark { position: fixed; right: 4vw; bottom: 8vh; z-index: 0; color: rgba(190,110,10,.08); font-size: 15vw; font-weight: 800; transform: rotate(-12deg); pointer-events: none; }
.theme-dark { --page-bg: #0c1118; --ink: #e9eff7; --muted: #9ba9ba; --line: #263341; --card: #121a23; --soft-blue: var(--primary-color-soft-strong, rgba(24,144,255,.18)); --soft-blue-strong: var(--primary-color-soft-strong, rgba(24,144,255,.18)); }.theme-dark .legacy-footer { background: var(--card); }.theme-dark .card-heading { background: linear-gradient(var(--soft-blue), var(--card)); }.theme-dark .change-row { border-color: var(--line); }.theme-dark .footer-inner a { color: var(--muted); }
.analysis-metric-grid, .analysis-factor-grid, .analysis-consensus-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }.analysis-metric-item, .analysis-factor-item, .analysis-consensus-grid > div { display: grid; gap: 4px; min-width: 0; padding: 9px 10px; border-radius: 8px; background: var(--soft-blue); }.analysis-metric-item small, .analysis-factor-item small, .analysis-consensus-grid small { color: var(--muted); font-size: 11px; }.analysis-metric-item strong, .analysis-factor-item strong, .analysis-consensus-grid strong { overflow-wrap: anywhere; color: var(--ink); font-size: 13px; }.analysis-positive { color: #1b9a6c !important; }.analysis-negative { color: #d55353 !important; }.analysis-neutral { color: var(--muted) !important; }.analysis-detail-list { display: grid; gap: 9px; margin-top: 12px; }.analysis-detail-item { padding: 11px 12px; border: 1px solid var(--line); border-radius: 9px; background: var(--page-bg); }.analysis-detail-item-title { display: flex; align-items: center; gap: 7px; color: var(--ink); font-size: 13px; }.analysis-detail-item-title .anticon { color: var(--blue); }.analysis-detail-item p { margin: 7px 0 0; color: var(--ink); font-size: 13px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }.analysis-bullet-list { display: grid; gap: 7px; margin: 12px 0 0; padding-left: 18px; color: var(--ink); font-size: 12px; line-height: 1.55; }.analysis-bullet-list li { overflow-wrap: anywhere; }.analysis-bullet-list li strong { margin-right: 6px; }.analysis-trend-list { display: grid; gap: 6px; margin-top: 12px; }.analysis-trend-item { display: grid; grid-template-columns: minmax(90px, 1fr) auto auto; align-items: center; gap: 8px; padding: 8px 10px; border-bottom: 1px solid var(--line); color: var(--muted); font-size: 12px; }.analysis-trend-item:last-child { border-bottom: 0; }.analysis-trend-item strong { font-size: 12px; }.analysis-trend-item small { color: var(--muted); }.analysis-risks { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--line); }.analysis-risks h4 { margin: 0; color: var(--ink); font-size: 13px; }
@media (max-width: 960px) { .legacy-main { width: 100%; }.analysis-controls { flex-wrap: wrap; align-items: stretch; }.control-spacer { display: none; }.date-control { flex: 1 1 100%; grid-template-columns: auto 118px; } }
@media (max-width: 900px) and (min-width: 681px) { .analysis-metric-grid, .analysis-factor-grid, .analysis-consensus-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .legacy-main { padding: 14px 12px 32px; }.date-control { grid-template-columns: auto 1fr; }.date-control .ant-select { width: 100%; }.daily-hero { align-items: flex-start; flex-direction: column; gap: 22px; padding: 25px 22px; }.daily-hero h1 { font-size: 32px; }.hero-audio { width: 100%; }.card-heading { align-items: flex-start; flex-direction: column; }.calendar-filters { flex-wrap: wrap; }.analysis-result-grid, .analysis-metric-grid, .analysis-factor-grid, .analysis-consensus-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.analysis-trend-item { grid-template-columns: 1fr auto; }.analysis-trend-item small { grid-column: 1 / -1; }.asset-analysis-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }.footer-inner { width: calc(100% - 24px); grid-template-columns: 1fr; }.footer-inner > div:last-child { justify-self: start; }.footer-bottom { width: calc(100% - 24px); flex-direction: column; } }
</style>

<style lang="less">
.asset-analysis-modal .ant-modal { max-width: calc(100vw - 24px); }
.asset-analysis-modal .ant-modal-content { overflow: hidden; border-radius: 14px; box-shadow: 0 20px 60px rgba(12, 28, 52, .22); }
.asset-analysis-modal .ant-modal-header { padding: 16px 20px; border-bottom-color: #e4eaf3; }
.asset-analysis-modal .ant-modal-body { padding: 18px 20px 20px; }
.asset-analysis-modal.theme-dark .ant-modal-content, .asset-analysis-modal.theme-dark .ant-modal-header { color: #eef4ff; border-color: #2a3547; background: #182235; }
.asset-analysis-modal.theme-dark .ant-modal-title, .asset-analysis-modal.theme-dark .ant-modal-close { color: #eef4ff; }
@media (max-width: 680px) { .asset-analysis-modal .ant-modal { width: calc(100vw - 16px) !important; max-width: calc(100vw - 16px); margin: 8px auto; }.asset-analysis-modal .ant-modal-header { padding: 14px 16px; }.asset-analysis-modal .ant-modal-body { max-height: calc(100vh - 72px); padding: 12px 10px 14px; }.asset-analysis-modal-body { max-height: calc(100vh - 112px); padding-right: 0; }.analysis-drawer-section { margin-top: 10px; padding: 11px; }.analysis-drawer-section-title h3 { font-size: 14px; }.analysis-copy p, .analysis-detail-item p, .analysis-evidence-item-copy { font-size: 12px; line-height: 1.55; }.analysis-metric-item, .analysis-factor-item, .analysis-consensus-grid > div { padding: 8px; }.analysis-metric-item strong, .analysis-factor-item strong, .analysis-consensus-grid strong { font-size: 12px; } }
</style>
