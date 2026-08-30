<template>
  <div class="strategy-ide-shell" :class="{ 'theme-dark': isDarkTheme }">
    <div class="strategy-ide-layout">
      <section class="script-panel script-panel--editor">
        <strategy-editor
          ref="scriptEditor"
          :key="editorKey"
          v-model="scriptCode"
          :is-dark="isDarkTheme"
          :visible="true"
          :user-id="userId"
          :strategy-id="currentSourceId"
          :script-source-id="currentSourceId"
          :asset-type="currentAssetType"
          :initial-template-key="scriptTemplateKey || editorInitialTemplateKey"
          :initial-param-schema="currentSourceParamSchema"
          :initial-param-values="scriptTemplateParams"
          :hidden-source="scriptCodeHidden"
          :readonly="false"
          :consume-copilot-draft="false"
          side-mode="split"
          @verified="scriptVerified = true"
          @template-change="handleTemplateChange"
        >
          <template #toolbar>
            <div class="ide-toolbar">
              <div class="toolbar-left">
                <div class="strategy-workspace-switcher">
                  <div class="strategy-workspace-copy">
                    <strong>{{ currentWorkspaceTitle }}</strong>
                    <span>{{ currentWorkspaceDescription }}</span>
                  </div>
                  <a-radio-group
                    :value="currentAssetType"
                    button-style="solid"
                  >
                    <a-radio-button value="script" @click="handleAssetTypeChange('script')">{{ text.ctaStrategy }}</a-radio-button>
                    <a-radio-button value="portfolio_strategy" @click="handleAssetTypeChange('portfolio_strategy')">{{ text.portfolioStrategy }}</a-radio-button>
                  </a-radio-group>
                </div>
                <a-select
                  class="script-select"
                  show-search
                  allow-clear
                  option-filter-prop="children"
                  :value="selectedScriptId"
                  :loading="loadingScripts"
                  :placeholder="text.selectScriptPlaceholder"
                  @change="handleScriptSelect"
                >
                  <a-select-option
                    v-for="item in scriptOptions"
                    :key="item.id"
                    :value="item.id"
                  >
                    {{ item.optionLabel }}
                  </a-select-option>
                </a-select>

                <a-tooltip :title="currentNewScriptLabel">
                  <a-button class="ide-icon-btn" @click="createNewDraft({ openTemplate: true })">
                    <a-icon type="plus" />
                  </a-button>
                </a-tooltip>
                <a-tooltip :title="text.refreshScripts">
                  <a-button class="ide-icon-btn" :loading="loadingScripts" @click="refreshSources">
                    <a-icon type="reload" />
                  </a-button>
                </a-tooltip>
                <a-tooltip :title="text.versionHistory">
                  <a-button
                    class="ide-icon-btn"
                    :disabled="!currentSourceId || scriptCodeHidden"
                    :loading="scriptVersionLoading"
                    @click="openVersionDrawer"
                  >
                    <a-icon type="history" />
                  </a-button>
                </a-tooltip>
                <a-tooltip v-if="currentSourceId" :title="text.saveAsNew">
                  <a-button
                    class="ide-icon-btn"
                    :loading="savingScriptMode === 'copy'"
                    :disabled="scriptCodeHidden || savingScript || deletingScript"
                    @click="saveScript(true)"
                  >
                    <a-icon type="copy" />
                  </a-button>
                </a-tooltip>
                <a-tooltip v-if="currentSourceId" :title="text.deleteScript">
                  <a-button
                    class="ide-icon-btn ide-icon-btn--danger"
                    :loading="deletingScript"
                    :disabled="savingScript"
                    @click="deleteCurrentSource"
                  >
                    <a-icon type="delete" />
                  </a-button>
                </a-tooltip>
                <a-button
                  class="script-save-button"
                  type="primary"
                  :loading="savingScriptMode === 'save'"
                  :disabled="scriptCodeHidden || savingScript || deletingScript || !hasUnsavedScriptChanges"
                  @click="saveScript(false)"
                >
                  {{ text.saveScript }}
                </a-button>
              </div>

              <div class="toolbar-right">
                <a-button
                  v-if="currentAssetType === 'portfolio_strategy'"
                  class="universe-library-button"
                  :class="{ 'universe-library-button--selected': currentAssetType === 'portfolio_strategy' && !!selectedUniverseId }"
                  @click="showUniverseLibrary = true"
                >
                  <a-icon type="cluster" />
                  {{ currentUniverseSummary || text.universeLibrary }}
                </a-button>
                <a-button class="factor-library-button" @click="showFactorLibrary = true">
                  <a-icon type="database" />
                  {{ text.factorLibrary }}
                </a-button>
                <a-button
                  v-if="currentAssetType === 'script'"
                  class="indicator-convert-button"
                  :loading="indicatorConvertIndicatorLoading"
                  @click="openIndicatorConvertPicker"
                >
                  <a-icon type="branches" />
                  {{ text.indicatorConvertEntry }}
                </a-button>
                <a-button class="script-backtest-button" @click="openBacktestCenter">
                  <a-icon type="bar-chart" />
                  {{ text.backtestTitle }}
                </a-button>
              </div>
            </div>
          </template>
        </strategy-editor>
      </section>
    </div>

    <a-modal
      :visible="showPublishModal"
      :title="text.publishModalTitle"
      :width="620"
      :confirmLoading="publishingScript"
      :ok-text="text.publishConfirm"
      :cancel-text="text.cancel"
      :wrap-class-name="isDarkTheme ? 'script-publish-modal script-publish-modal--dark' : 'script-publish-modal'"
      @ok="confirmPublish"
      @cancel="closePublishModal"
    >
      <div class="publish-form">
        <div class="publish-summary-card">
          <div class="publish-summary-icon">
            <a-icon type="shop" />
          </div>
          <div class="publish-summary-main">
            <div class="publish-summary-label">{{ text.publishModalTitle }}</div>
            <div class="publish-summary-name">{{ publishForm.name || deriveScriptName() }}</div>
          </div>
          <a-tag class="publish-summary-tag" color="red">{{ text.marketTag }}</a-tag>
        </div>

        <div class="publish-note">
          <a-icon type="info-circle" />
          <span>{{ text.publishHint }}</span>
        </div>

        <div class="publish-section">
          <div class="publish-section-title">{{ text.publishName }}</div>
          <a-input v-model="publishForm.name" :placeholder="text.publishNamePlaceholder" />
        </div>

        <a-alert type="success" show-icon>
          <template slot="message">{{ text.publishFree }} · {{ $t('community.codeVisible') }}</template>
        </a-alert>

        <div class="publish-section">
          <div class="publish-section-title">{{ text.publishDescription }}</div>
          <a-textarea
            v-model="publishForm.description"
            class="publish-description-input"
            :placeholder="text.publishDescriptionPlaceholder"
            :auto-size="{ minRows: 4, maxRows: 7 }"
          />
        </div>
      </div>
    </a-modal>

    <a-modal
      :visible="showIndicatorConvertModal"
      :title="text.indicatorConvertTitle"
      :confirmLoading="indicatorConvertLoading"
      :ok-text="text.indicatorConvertConfirm"
      :cancel-text="text.cancel"
      :wrap-class-name="isDarkTheme ? 'indicator-convert-modal indicator-convert-modal--dark' : 'indicator-convert-modal'"
      @ok="confirmIndicatorToStrategy"
      @cancel="closeIndicatorConvertModal"
    >
      <div class="indicator-convert-box">
        <div class="indicator-convert-selector">
          <label class="field-label">{{ text.indicatorConvertSelect }}</label>
          <a-select
            v-model="selectedIndicatorConvertId"
            show-search
            option-filter-prop="children"
            style="width: 100%"
            :loading="indicatorConvertIndicatorLoading"
            :placeholder="text.indicatorConvertSelectPlaceholder"
            @change="handleIndicatorConvertSelect"
          >
            <a-select-option
              v-for="item in indicatorConvertIndicators"
              :key="String(item.indicatorId)"
              :value="String(item.indicatorId)"
              :disabled="item.codeHidden || !item.code"
            >
              {{ item.name || text.defaultIndicatorName }}
              <template v-if="item.symbol"> - {{ item.symbol }}</template>
              <template v-if="item.codeHidden || !item.code"> - {{ text.indicatorConvertNoCodeShort }}</template>
            </a-select-option>
          </a-select>
        </div>

        <div v-if="indicatorConvertContext" class="indicator-convert-current">
          <div>
            <span>{{ text.indicatorConvertSource }}</span>
            <strong>{{ indicatorConvertContext.name || text.defaultIndicatorName }}</strong>
          </div>
          <small>
            {{ marketLabel(indicatorConvertContext.market) }}
            <template v-if="indicatorConvertContext.symbol"> / {{ indicatorConvertContext.symbol }}</template>
            <template v-if="indicatorConvertContext.timeframe"> / {{ indicatorConvertContext.timeframe }}</template>
          </small>
        </div>

        <a-alert
          v-else
          type="info"
          show-icon
          :message="text.indicatorConvertSelectFirst"
        />

        <label class="field-label field-label--spaced">{{ text.indicatorConvertInstruction }}</label>
        <a-textarea
          v-model="indicatorConvertInstruction"
          :auto-size="{ minRows: 5, maxRows: 8 }"
          :placeholder="text.indicatorConvertPlaceholder"
        />
        <div class="indicator-convert-note">
          <a-icon type="info-circle" />
          <span>{{ text.indicatorConvertBoundary }}</span>
        </div>
        <a-alert
          v-if="indicatorConvertError"
          type="error"
          show-icon
          :message="indicatorConvertError"
        />
      </div>
    </a-modal>

    <factor-library-modal
      :visible="showFactorLibrary"
      :is-dark="isDarkTheme"
      :asset-type="currentAssetType"
      @close="showFactorLibrary = false"
    />

    <universe-library-modal
      :visible="showUniverseLibrary"
      :is-dark="isDarkTheme"
      :asset-type="currentAssetType"
      :selected-universe-id="selectedUniverseId"
      @use="handleUniverseUse"
      @close="showUniverseLibrary = false"
    />

    <a-drawer
      :visible="showVersionDrawer"
      :title="text.versionHistory"
      :width="640"
      :wrap-class-name="isDarkTheme ? 'script-version-drawer script-version-drawer--dark' : 'script-version-drawer'"
      @close="showVersionDrawer = false"
    >
      <a-spin :spinning="scriptVersionLoading">
        <div class="code-version-toolbar">
          <span>{{ currentSourceName || text.defaultName }}</span>
          <a-button size="small" icon="reload" @click="loadScriptVersions">{{ text.refreshScripts }}</a-button>
        </div>
        <a-empty v-if="!scriptVersions.length" :description="text.versionEmpty" />
        <div v-else class="code-version-list">
          <div v-for="item in scriptVersions" :key="item.id" class="code-version-item">
            <div class="code-version-item__main">
              <strong>{{ text.versionNo.replace('{version}', item.version_no) }}</strong>
              <span>{{ item.name || currentSourceName }}</span>
              <small>{{ formatTime(item.created_at) }}</small>
            </div>
            <div class="code-version-item__actions">
              <a-button
                size="small"
                :disabled="scriptCodeHidden"
                @click="previewScriptVersion(item)"
              >
                {{ text.versionPreview }}
              </a-button>
              <a-button
                size="small"
                type="primary"
                :loading="restoringScriptVersionId === item.id"
                :disabled="scriptCodeHidden || item.restore_disabled"
                @click="confirmRestoreScriptVersion(item)"
              >
                {{ text.versionRestore }}
              </a-button>
            </div>
          </div>
        </div>
      </a-spin>

      <div v-if="scriptVersionPreview" class="code-version-preview">
        <div class="code-version-preview__head">
          <strong>{{ text.versionPreviewTitle.replace('{version}', scriptVersionPreview.version_no) }}</strong>
          <a-button size="small" icon="close" @click="scriptVersionPreview = null" />
        </div>
        <pre>{{ scriptVersionPreview.code }}</pre>
      </div>
    </a-drawer>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import StrategyEditor from './components/StrategyEditor.vue'
import FactorLibraryModal from './FactorLibraryModal.vue'
import UniverseLibraryModal from './UniverseLibraryModal.vue'
import { resolveIndicatorStrategyContext } from '@/utils/indicatorStrategyContext'
import {
  aiGenerateStrategy,
  createScriptSource,
  deleteScriptSource,
  getStrategyBacktestHistory,
  getIndicatorListForStrategy,
  getScriptSourceDetail,
  getScriptSourceList,
  getScriptSourceVersion,
  getScriptSourceVersions,
  publishScriptSource,
  restoreScriptSourceVersion,
  updateScriptSource,
  verifyStrategyCode
} from '@/api/strategy'

const DEFAULT_SCRIPT_CODE = `"""
My Custom Strategy

Describe the strategy logic, supported markets, entry/exit rules, and risk controls here.
"""

def initialize(context):
    context.set_universe(["USStock:SPY"])
    context.subscribe(frequency="1d")
    context.set_warmup(55)
    g.period = 50

def handle_data(context, data):
    bars = get_history(g.period + 2, "1d", "close", "USStock:SPY")
    if len(bars) < g.period:
        return
    average = float(bars["close"].tail(g.period).mean())
    target = 1.0 if float(bars["close"].iloc[-1]) > average else 0.0
    order_target_percent("USStock:SPY", target, reason="single_ma_regime")
`

const DEFAULT_PORTFOLIO_CODE = `"""
My Portfolio Strategy

Rank the eligible point-in-time universe by momentum and hold an equal-weight Top-N portfolio.
"""

def initialize(context):
    context.set_universe(pool="nasdaq100")
    context.subscribe(frequency="1d")
    context.set_warmup(130)
    g.top_n = 10
    g.lookback = 126
    run_weekly(rebalance, weekday=1, time="09:35")

def rebalance(context, data):
    scores = {}
    for symbol in get_universe_stocks():
        frame = get_history(g.lookback + 1, "1d", "close", symbol)
        if len(frame) <= g.lookback:
            continue
        start = float(frame["close"].iloc[-g.lookback - 1])
        end = float(frame["close"].iloc[-1])
        if start > 0:
            scores[symbol] = end / start - 1.0
    selected = sorted(scores, key=scores.get, reverse=True)[:g.top_n]
    for symbol in get_positions().keys():
        if symbol not in selected:
            order_target_percent(symbol, 0.0, reason="left_top_n")
    weight = 1.0 / len(selected) if selected else 0.0
    for symbol in selected:
        order_target_percent(symbol, weight, reason="momentum_top_n")
`

export default {
  name: 'StrategyIde',
  components: {
    StrategyEditor,
    FactorLibraryModal,
    UniverseLibraryModal
  },
  data () {
    return {
      scriptSources: [],
      loadingScripts: false,
      selectedScriptId: undefined,
      currentSourceId: null,
      currentSource: null,
      currentAssetType: 'script',
      scriptCode: DEFAULT_SCRIPT_CODE,
      scriptCodeHidden: false,
      scriptTemplateKey: '',
      scriptTemplateParams: {},
      scriptParamSchema: {},
      editorInitialTemplateKey: '',
      editorKeySeed: 0,
      scriptVerified: false,
      savingScript: false,
      savingScriptMode: '',
      deletingScript: false,
      publishingScript: false,
      showPublishModal: false,
      publishForm: {
        name: '',
        description: ''
      },
      showVersionDrawer: false,
      scriptVersionLoading: false,
      scriptVersions: [],
      scriptVersionPreview: null,
      restoringScriptVersionId: null,
      showFactorLibrary: false,
      showUniverseLibrary: false,
      showIndicatorConvertModal: false,
      indicatorConvertLoading: false,
      indicatorConvertIndicatorLoading: false,
      indicatorConvertIndicators: [],
      selectedIndicatorConvertId: undefined,
      indicatorConvertContext: null,
      indicatorConvertInstruction: '',
      indicatorConvertError: '',
      runConfig: {
        market_category: 'Crypto',
        exchange_id: 'binance',
        symbol: 'BTC/USDT',
        timeframe: '1m',
        market_type: 'swap',
        trade_direction: 'long',
        initial_capital: 10000,
        leverage: 5
      },
      lastSavedSnapshot: ''
    }
  },
  computed: {
    ...mapState({
      navTheme: state => state.app.theme
    }),
    isDarkTheme () {
      const body = typeof document !== 'undefined' ? document.body : null
      return this.navTheme === 'dark' ||
        this.navTheme === 'realdark' ||
        !!(body && (body.classList.contains('dark') || body.classList.contains('realdark')))
    },
    isZh () {
      return String((this.$i18n && this.$i18n.locale) || '').toLowerCase().startsWith('zh')
    },
    userId () {
      const userInfo = this.$store && this.$store.getters && this.$store.getters.userInfo
      return (userInfo && userInfo.id) || 1
    },
    editorKey () {
      return `script-editor-${this.currentSourceId || 'draft'}-${this.editorKeySeed}`
    },
    currentSourceName () {
      return (this.currentSource && (this.currentSource.name || this.currentSource.strategy_name)) ||
        this.extractScriptMetadataFromCode(this.scriptCode).name ||
        ''
    },
    currentSourceParamSchema () {
      if (this.scriptParamSchema && Array.isArray(this.scriptParamSchema.params) && this.scriptParamSchema.params.length) {
        return this.scriptParamSchema
      }
      const source = this.currentSource || {}
      const direct = this.parseObject(source.param_schema)
      if (Array.isArray(direct.params) && direct.params.length) return direct
      if (Array.isArray(source.params) && source.params.length) return { params: source.params }
      const metadata = this.parseObject(source.metadata)
      const metaSchema = this.parseObject(metadata.param_schema)
      if (Array.isArray(metaSchema.params) && metaSchema.params.length) return metaSchema
      return direct
    },
    allScriptOptions () {
      return (this.scriptSources || []).map(item => {
        const id = this.getScriptSourceId(item)
        return {
          ...item,
          id,
          optionLabel: item.name || item.strategy_name || `Script #${id}`
        }
      }).filter(item => item.id)
    },
    scriptOptions () {
      return this.allScriptOptions.filter(item => item.asset_type === this.currentAssetType)
    },
    selectedUniverseId () {
      return Number(this.runConfig && (this.runConfig.universe_id || this.runConfig.universeId)) || undefined
    },
    currentUniverseSummary () {
      if (this.currentAssetType !== 'portfolio_strategy' || !this.selectedUniverseId) return ''
      const label = String((this.runConfig && (this.runConfig.universe_name || this.runConfig.universeName || this.runConfig.universe_code || this.runConfig.universeCode)) || this.selectedUniverseId)
      return this.text.universeSelected.replace('{name}', label)
    },
    currentWorkspaceTitle () {
      return this.currentAssetType === 'portfolio_strategy' ? this.text.portfolioWorkspaceTitle : this.text.ctaWorkspaceTitle
    },
    currentWorkspaceDescription () {
      return this.currentAssetType === 'portfolio_strategy' ? this.text.portfolioWorkspaceDescription : this.text.ctaWorkspaceDescription
    },
    currentNewScriptLabel () {
      return this.currentAssetType === 'portfolio_strategy' ? this.text.newPortfolioStrategy : this.text.newCtaStrategy
    },
    hasUnsavedScriptChanges () {
      if (this.scriptCodeHidden) return false
      if (!this.currentSourceId) return !!String(this.scriptCode || '').trim()
      return this.lastSavedSnapshot !== this.scriptSnapshot()
    },
    text () {
      return [
        'selectScriptLabel',
        'selectScriptPlaceholder',
        'ctaStrategy',
        'portfolioStrategy',
        'newScript',
        'refreshScripts',
        'saveScript',
        'saveAsNew',
        'publishScript',
        'deleteScript',
        'createLive',
        'backtestTitle',
        'cancel',
        'defaultName',
        'autoNameSuffix',
        'codeRequired',
        'hiddenScriptTitle',
        'hiddenScriptDesc',
        'loadScriptsFailed',
        'loadScriptFailed',
        'saveSuccess',
        'saveFailed',
        'deleteSuccess',
        'deleteFailed',
        'deleteConfirmTitle',
        'deleteConfirmDesc',
        'runningEditBlocked',
        'verifyPassed',
        'verifyBlocked',
        'verifyFailed',
        'publishSuccess',
        'publishFailed',
        'publishBacktestRequired',
        'publishModalTitle',
        'publishConfirm',
        'marketTag',
        'publishHint',
        'publishName',
        'publishNamePlaceholder',
        'publishPricingType',
        'publishFree',
        'publishPaid',
        'publishPrice',
        'publishDescription',
        'publishDescriptionPlaceholder',
        'priceRequired',
        'publishVipFree',
        'publishVipFreeHint',
        'publishHideCode',
        'publishHideCodeHint',
        'versionHistory',
        'versionEmpty',
        'versionNo',
        'versionPreview',
        'versionRestore',
        'versionRestoreTitle',
        'versionRestoreContent',
        'versionPreviewTitle',
        'versionRestored',
        'versionHiddenBlocked',
        'versionLoadFailed',
        'versionRestoreFailed',
        'indicatorConvertEntry',
        'indicatorConvertTitle',
        'indicatorConvertConfirm',
        'indicatorConvertSelect',
        'indicatorConvertSelectPlaceholder',
        'indicatorConvertSelectFirst',
        'indicatorConvertSource',
        'indicatorConvertInstruction',
        'indicatorConvertPlaceholder',
        'indicatorConvertBoundary',
        'indicatorConvertNoCodeShort',
        'indicatorConvertNoCode',
        'indicatorConvertHiddenBlocked',
        'indicatorConvertFailed',
        'indicatorConvertSuccess',
        'defaultIndicatorName',
        'noChangesToSave',
        'factorLibrary',
        'universeLibrary',
        'universeSelected',
        'workspaceLabel',
        'ctaWorkspaceTitle',
        'ctaWorkspaceDescription',
        'portfolioWorkspaceTitle',
        'portfolioWorkspaceDescription',
        'newCtaStrategy',
        'newPortfolioStrategy',
        'switchWorkspaceTitle',
        'switchWorkspaceContent',
        'universeApplied'
      ].reduce((acc, key) => {
        acc[key] = this.$t(`strategyIde.${key}`)
        return acc
      }, {})
    }
  },
  watch: {
    scriptCode () {
      this.scriptVerified = false
    }
  },
  mounted () {
    this._saveShortcut = (event) => this.handleSaveShortcut(event)
    window.addEventListener('keydown', this._saveShortcut, true)
    this.initPage()
  },
  beforeDestroy () {
    if (this._saveShortcut) {
      window.removeEventListener('keydown', this._saveShortcut, true)
      this._saveShortcut = null
    }
  },
  methods: {
    async initPage () {
      await this.loadSources()
      if (this.isIndicatorConvertRoute()) {
        this.createNewDraft({
          openTemplate: false,
          updateRoute: false,
          assetType: 'script'
        })
        await this.applyIndicatorConvertRouteOnce()
        return
      }
      if (this.isDraftRoute() || this.hasCopilotScriptDraft()) {
        this.createNewDraft({
          openTemplate: this.shouldOpenTemplateFromRoute(),
          updateRoute: false,
          assetType: this.getRouteAssetType()
        })
        this.applyCopilotScriptDraft()
        if (this.isLegacyAiDraftRoute() || this.hasRouteSourceId()) {
          this.writeDraftRoute({ openTemplate: this.shouldOpenTemplateFromRoute() })
        }
        this.applyIndicatorConvertRouteOnce()
        return
      }
      const routeId = this.getInitialRouteSourceId()
      const hasRouteSource = routeId && this.allScriptOptions.some(item => String(item.id) === String(routeId))
      const firstId = this.scriptOptions.length ? this.scriptOptions[0].id : ''
      if (hasRouteSource) {
        await this.openSource(routeId, { updateRoute: false })
      } else if (firstId) {
        await this.openSource(firstId, { updateRoute: true })
      } else {
        this.createNewDraft({ openTemplate: false })
      }
      this.applyIndicatorConvertRouteOnce()
    },
    async loadSources () {
      this.loadingScripts = true
      try {
        const res = await getScriptSourceList()
        this.scriptSources = this.extractSources(res)
      } catch (e) {
        this.$message.warning(this.text.loadScriptsFailed)
      } finally {
        this.loadingScripts = false
      }
    },
    async refreshSources () {
      await this.loadSources()
      if (this.currentSourceId) {
        await this.openSource(this.currentSourceId, { updateRoute: false })
      }
    },
    extractSources (res) {
      const data = res && res.data
      if (Array.isArray(data)) return data
      if (data && Array.isArray(data.items)) return data.items
      return []
    },
    getInitialRouteSourceId () {
      const query = this.$route.query || {}
      const value = query.sourceId
      return value ? String(value).trim() : ''
    },
    getRouteAssetType () {
      const query = this.$route.query || {}
      return String(query.assetType || '').trim() === 'portfolio_strategy' ? 'portfolio_strategy' : 'script'
    },
    isDraftRoute () {
      const query = this.$route.query || {}
      return String(query.draft || '') === '1' || this.isLegacyAiDraftRoute()
    },
    isLegacyAiDraftRoute () {
      const query = this.$route.query || {}
      return String(query.aiDraft || '') === '1'
    },
    isIndicatorConvertRoute () {
      const query = this.$route.query || {}
      return String(query.convert || '').toLowerCase() === 'indicator' ||
        !!query.convert_key ||
        !!query.source_indicator_id ||
        !!query.indicator_id
    },
    hasRouteSourceId () {
      return !!this.getInitialRouteSourceId()
    },
    hasCopilotScriptDraft () {
      if (typeof sessionStorage === 'undefined') return false
      try {
        return !!String(sessionStorage.getItem('qd_strategy_source') || '').trim()
      } catch (_) {
        return false
      }
    },
    applyCopilotScriptDraft () {
      if (typeof sessionStorage === 'undefined') return
      let code = ''
      let meta = {}
      try {
        code = String(sessionStorage.getItem('qd_strategy_source') || '').trim()
        const rawMeta = sessionStorage.getItem('qd_copilot_script_strategy_meta') || ''
        meta = rawMeta ? JSON.parse(rawMeta) : {}
        if (code) {
          sessionStorage.removeItem('qd_strategy_source')
          sessionStorage.removeItem('qd_copilot_script_strategy_meta')
        }
      } catch (_) {
        meta = {}
      }
      if (!code) return
      this.currentSource = null
      this.currentSourceId = null
      this.selectedScriptId = undefined
      this.scriptCodeHidden = false
      this.scriptCode = code
      this.scriptTemplateKey = ''
      this.scriptTemplateParams = {}
      this.scriptParamSchema = {}
      this.editorInitialTemplateKey = ''
      this.scriptVerified = false
      this.lastSavedSnapshot = ''
      this.runConfig = {
        ...this.runConfig,
        market_category: meta.market || this.runConfig.market_category,
        symbol: meta.symbol || this.runConfig.symbol
      }
    },
    shouldOpenTemplateFromRoute () {
      const query = this.$route.query || {}
      return String(query.template_picker || '') === '1'
    },
    getScriptSourceId (item) {
      if (!item) return ''
      return String(item.id || '').trim()
    },
    async handleScriptSelect (id) {
      if (!id) {
        this.createNewDraft({ openTemplate: false })
        return
      }
      await this.openSource(id, { updateRoute: true })
    },
    async openSource (id, options = {}) {
      const sourceId = String(id || '').trim()
      if (!sourceId) return
      try {
        const res = await getScriptSourceDetail(sourceId)
        const source = (res && res.data) || res
        if (!source || !this.getScriptSourceId(source)) {
          throw new Error(this.text.loadScriptFailed)
        }
        this.applySource(source)
        if (options.updateRoute !== false) {
          this.writeRouteSource(this.currentSourceId)
        }
      } catch (e) {
        this.$message.error(e.backendMessage || e.message || this.text.loadScriptFailed)
      }
    },
    applySource (source) {
      const metadata = this.parseObject(source.metadata)
      const runConfig = this.parseObject(metadata.last_run_config)
      this.currentSource = source
      this.currentAssetType = source.asset_type === 'portfolio_strategy' ? 'portfolio_strategy' : 'script'
      this.currentSourceId = this.getScriptSourceId(source)
      this.selectedScriptId = this.currentSourceId ? String(this.currentSourceId) : undefined
      this.scriptCodeHidden = false
      this.scriptCode = String(source.code || (this.currentAssetType === 'portfolio_strategy' ? DEFAULT_PORTFOLIO_CODE : DEFAULT_SCRIPT_CODE))
      this.scriptTemplateKey = source.template_key || runConfig.script_template_key || ''
      this.scriptTemplateParams = {
        ...this.parseObject(metadata.script_template_params),
        ...this.parseObject(runConfig.script_template_params)
      }
      this.scriptParamSchema = this.parseObject(source.param_schema)
      this.runConfig = {
        ...this.runConfig,
        ...runConfig
      }
      const universeReference = this.extractUniverseReferenceFromCode(this.scriptCode)
      if (universeReference.id && !this.runConfig.universe_id) {
        this.runConfig = {
          ...this.runConfig,
          universe_id: universeReference.id,
          universe_code: universeReference.code
        }
      }
      this.editorInitialTemplateKey = ''
      this.editorKeySeed += 1
      this.scriptVerified = !!(metadata.lifecycle_verified || metadata.script_verified)
      this.lastSavedSnapshot = this.scriptSnapshot()
    },
    createNewDraft ({ openTemplate = false, updateRoute = true, assetType = this.currentAssetType } = {}) {
      this.currentSource = null
      this.currentSourceId = null
      this.selectedScriptId = undefined
      this.currentAssetType = assetType === 'portfolio_strategy' ? 'portfolio_strategy' : 'script'
      this.scriptCode = this.currentAssetType === 'portfolio_strategy' ? DEFAULT_PORTFOLIO_CODE : DEFAULT_SCRIPT_CODE
      this.scriptCodeHidden = false
      this.scriptTemplateKey = ''
      this.scriptTemplateParams = {}
      this.scriptParamSchema = {}
      this.editorInitialTemplateKey = ''
      this.scriptVerified = false
      this.runConfig = {
        ...this.runConfig,
        universe_id: undefined,
        universe_code: '',
        universe_name: ''
      }
      this.lastSavedSnapshot = ''
      this.editorKeySeed += 1
      if (updateRoute) this.writeDraftRoute({ openTemplate })
      if (openTemplate) {
        this.$nextTick(() => {
          const editor = this.$refs.scriptEditor
          if (editor && typeof editor.openTemplatePicker === 'function') {
            editor.openTemplatePicker()
          }
        })
      }
    },
    handleAssetTypeChange (assetType) {
      const target = assetType === 'portfolio_strategy' ? 'portfolio_strategy' : 'script'
      if (target === this.currentAssetType) return
      const switchWorkspace = async () => {
        this.currentAssetType = target
        const first = this.allScriptOptions.find(item => item.asset_type === target)
        if (first) await this.openSource(first.id, { updateRoute: true })
        else this.createNewDraft({ openTemplate: false, updateRoute: true, assetType: target })
      }
      const defaultCode = this.currentAssetType === 'portfolio_strategy' ? DEFAULT_PORTFOLIO_CODE : DEFAULT_SCRIPT_CODE
      const shouldConfirm = this.currentSourceId
        ? this.hasUnsavedScriptChanges
        : String(this.scriptCode || '').trim() !== String(defaultCode).trim()
      if (shouldConfirm) {
        this.$confirm({
          title: this.text.switchWorkspaceTitle,
          content: this.text.switchWorkspaceContent,
          okText: this.text.switchWorkspaceTitle,
          cancelText: this.text.cancel,
          onOk: switchWorkspace
        })
        return
      }
      switchWorkspace()
    },
    extractUniverseReferenceFromCode (code) {
      const source = String(code || '')
      const poolMatch = source.match(/context\.set_universe\(pool=["']([^"']+)["']\)/i)
      if (poolMatch) return { id: undefined, code: String(poolMatch[1] || '').trim() }
      const indexMatch = source.match(/context\.set_universe\(index=["']INDEX:([^"']+)["']\)/i)
      return indexMatch ? { id: undefined, code: String(indexMatch[1] || '').trim() } : { id: undefined, code: '' }
    },
    applyUniverseReferenceToCode (item) {
      if (this.scriptCodeHidden) return
      const pool = String(item.code || '').trim().toLowerCase()
      const line = `context.set_universe(pool="${pool}")`
      const pattern = /context\.set_universe\((?:pool=["'][^"']+["']|index=["']INDEX:[^"']+["'])\)/i
      const code = String(this.scriptCode || '')
      if (pattern.test(code)) {
        this.scriptCode = code.replace(pattern, line)
        return
      }
      const initPattern = /^(def\s+initialize\s*\([^)]*\):\s*)$/m
      this.scriptCode = initPattern.test(code) ? code.replace(initPattern, `$1\n    ${line}`) : `${line}\n${code}`
    },
    handleUniverseUse (item) {
      if (!item || this.currentAssetType !== 'portfolio_strategy') return
      this.runConfig = {
        ...this.runConfig,
        universe_id: Number(item.id),
        universe_code: item.code || '',
        universe_name: item.name || item.code || ''
      }
      this.applyUniverseReferenceToCode(item)
      this.showUniverseLibrary = false
      this.$message.success(this.text.universeApplied.replace('{name}', item.name || item.code || ''))
    },
    writeRouteSource (sourceId) {
      if (!sourceId) return
      const query = { tab: 'script', sourceId: String(sourceId), assetType: this.currentAssetType }
      this.replaceRouteQuery(query)
    },
    writeDraftRoute ({ openTemplate = false } = {}) {
      const query = { tab: 'script', draft: '1', assetType: this.currentAssetType }
      if (openTemplate) query.template_picker = '1'
      else delete query.template_picker
      this.replaceRouteQuery(query)
    },
    replaceRouteQuery (query) {
      const clean = {}
      Object.keys(query || {}).forEach(key => {
        const value = query[key]
        if (value !== undefined && value !== null && String(value) !== '') {
          clean[key] = value
        }
      })
      const current = JSON.stringify(this.$route.query || {})
      const next = JSON.stringify(clean)
      if (current !== next) {
        this.$router.replace({ path: '/strategy-ide', query: clean }).catch(() => {})
      }
    },
    parseObject (value) {
      if (!value) return {}
      if (typeof value === 'object' && !Array.isArray(value)) return { ...value }
      if (typeof value === 'string') {
        try {
          const parsed = JSON.parse(value)
          return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
        } catch (_) {
          return {}
        }
      }
      return {}
    },
    handleTemplateChange (payload) {
      this.scriptTemplateKey = (payload && payload.key) || ''
      this.scriptTemplateParams = payload && payload.params && typeof payload.params === 'object'
        ? { ...payload.params }
        : {}
      this.scriptParamSchema = payload && payload.param_schema && typeof payload.param_schema === 'object'
        ? { ...payload.param_schema }
        : {}
      if (this.scriptCodeHidden) {
        this.runConfig = {
          ...this.runConfig,
          script_template_key: this.scriptTemplateKey,
          script_template_params: { ...this.scriptTemplateParams }
        }
      }
      this.scriptVerified = false
    },
    handleSaveShortcut (event) {
      if (!event || !(event.ctrlKey || event.metaKey) || String(event.key || '').toLowerCase() !== 's') return
      event.preventDefault()
      this.saveScript(false)
    },
    extractScriptMetadataFromCode (code) {
      const source = String(code || '')
      const doc = source.match(/^\s*(?:[rubfRUBF]*)("""|''')([\s\S]*?)\1/)
      if (doc) {
        const lines = String(doc[2] || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean)
        if (lines.length) {
          return {
            name: lines[0],
            description: lines.slice(1).join('\n')
          }
        }
      }
      const nameMatch = source.match(/^\s*(?:my_strategy_name|strategy_name)\s*=\s*(['"])(.*?)\1\s*$/m)
      const descMatch = source.match(/^\s*(?:my_strategy_description|strategy_description)\s*=\s*(['"])(.*?)\1\s*$/m)
      return {
        name: nameMatch ? nameMatch[2] : '',
        description: descMatch ? descMatch[2] : ''
      }
    },
    deriveScriptName () {
      const meta = this.extractScriptMetadataFromCode(this.scriptCode)
      if (meta.name) return meta.name
      if (this.currentSource && this.currentSource.name) return this.currentSource.name
      return this.text.defaultName
    },
    getCurrentScriptCode () {
      const editor = this.$refs.scriptEditor
      if (editor && typeof editor.getCode === 'function') {
        return String(editor.getCode() || '')
      }
      return String(this.scriptCode || '')
    },
    extractScriptTimeframeFromCode (code) {
      const source = String(code || '')
      const match = source.match(/(?:^|\n)\s*#\s*timeframe\s*:\s*([A-Za-z0-9_-]+)/i)
      if (!match) return ''
      const raw = String(match[1] || '').trim()
      const aliases = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1H',
        '4h': '4H',
        '1d': '1D',
        '1w': '1W'
      }
      return aliases[raw.toLowerCase()] || ''
    },
    buildTradingConfig () {
      const cfg = this.runConfig || {}
      const marketCategory = cfg.market_category || cfg.marketCategory || 'Crypto'
      const marketType = marketCategory === 'Crypto' && cfg.market_type === 'swap' ? 'swap' : 'spot'
      const tradeDirection = marketType === 'spot' ? 'long' : (cfg.trade_direction || 'long')
      const investmentAmount = Number(cfg.initial_capital || cfg.investment_amount || 10000)
      const codeTimeframe = this.extractScriptTimeframeFromCode(this.getCurrentScriptCode())
      const out = {
        market_category: marketCategory,
        exchange_id: marketCategory === 'Crypto' ? String(cfg.exchange_id || 'binance').toLowerCase() : '',
        symbol: String(cfg.symbol || 'BTC/USDT').trim(),
        timeframe: codeTimeframe || cfg.timeframe || '1m',
        tick_interval_sec: 10,
        market_type: marketType,
        trade_direction: tradeDirection,
        initial_capital: investmentAmount,
        investment_amount: investmentAmount,
        leverage: marketType === 'spot' ? 1 : Number(cfg.leverage || 5)
      }
      ;['strategy_family', 'executor_type', 'executor_config', 'executor_preview', 'bot_type', 'bot_params'].forEach(key => {
        if (cfg[key] !== undefined && cfg[key] !== null) out[key] = cfg[key]
      })
      if (cfg.tick_interval_sec) out.tick_interval_sec = Number(cfg.tick_interval_sec)
      if (this.scriptTemplateKey) out.script_template_key = this.scriptTemplateKey
      if (this.scriptTemplateParams && Object.keys(this.scriptTemplateParams).length) {
        out.script_template_params = { ...this.scriptTemplateParams }
      }
      if (this.currentAssetType === 'portfolio_strategy') {
        const universeReference = this.extractUniverseReferenceFromCode(this.getCurrentScriptCode())
        const universeId = Number(universeReference.id || cfg.universe_id || cfg.universeId) || undefined
        if (universeId) {
          out.universe_id = universeId
          out.universe_code = universeReference.code || cfg.universe_code || cfg.universeCode || ''
          out.universe_name = cfg.universe_name || cfg.universeName || ''
        }
      }
      return out
    },
    buildPayload () {
      const currentCode = this.getCurrentScriptCode()
      const meta = this.extractScriptMetadataFromCode(currentCode)
      const description = meta.description || (this.currentSource && this.currentSource.description) || ''
      return {
        name: meta.name || this.deriveScriptName(),
        description,
        code: currentCode,
        asset_type: this.currentAssetType,
        template_key: this.scriptTemplateKey,
        param_schema: this.currentSourceParamSchema,
        template_params: { ...this.scriptTemplateParams },
        metadata: {
          description,
          last_run_config: this.buildTradingConfig(),
          script_template_params: { ...this.scriptTemplateParams },
          lifecycle_verified: this.scriptVerified,
          script_verified: this.scriptVerified
        }
      }
    },
    scriptSnapshot () {
      return JSON.stringify({
        code: String(this.scriptCode || ''),
        asset_type: this.currentAssetType,
        template_key: this.scriptTemplateKey || '',
        template_params: { ...(this.scriptTemplateParams || {}) },
        universe_id: this.selectedUniverseId || null
      })
    },
    validateScriptCode () {
      if (this.scriptCodeHidden) return true
      if (!String(this.scriptCode || '').trim()) {
        this.$message.warning(this.text.codeRequired)
        return false
      }
      return true
    },
    async verifyScriptCode (options = {}) {
      const code = String(this.scriptCode || '').trim()
      if (!code) {
        this.$message.error(this.text.verifyBlocked.replace('{reason}', this.text.codeRequired))
        return false
      }
      try {
        const res = await verifyStrategyCode({ code })
        const verification = (res && res.data) || {}
        if (!(res && res.code === 1 && verification.valid)) {
          const reason = verification.error || (res && res.msg) || this.text.verifyFailed
          this.$message.error(this.text.verifyBlocked.replace('{reason}', reason))
          return false
        }
        this.scriptVerified = true
        if (!options.silentSuccess) this.$message.success(this.text.verifyPassed)
        return true
      } catch (e) {
        this.$message.error(`${this.text.verifyFailed}: ${e.backendMessage || e.message || ''}`)
        return false
      }
    },
    formatVerifyHint (hint) {
      if (!hint || !hint.code) return ''
      const params = hint.params || {}
      const calls = Array.isArray(params.calls) ? params.calls : []
      const names = calls.map(item => item && item.name).filter(Boolean).join(', ')
      const key = `strategyIde.verifyHints.${hint.code}`
      const translated = this.$t(key, {
        count: params.count || 0,
        names
      })
      return translated && translated !== key ? translated : hint.code
    },
    async saveScript (forceCreate = false, options = {}) {
      if (this.scriptCodeHidden) {
        if (!options.silent) this.$message.info(this.text.hiddenScriptDesc)
        return null
      }
      if (!this.validateScriptCode()) return null
      if (!forceCreate && this.currentSource && this.currentSource.status === 'running') {
        this.$message.warning(this.text.runningEditBlocked)
        return null
      }
      if (!forceCreate && this.currentSourceId && !this.hasUnsavedScriptChanges) {
        if (!options.silent && !options.skipUnchanged) {
          this.$message.info(this.text.noChangesToSave)
        }
        return this.currentSourceId
      }
      if (this.savingScript) return null
      this.savingScript = true
      this.savingScriptMode = options.loadingMode || (forceCreate ? 'copy' : 'save')
      try {
        const payload = this.buildPayload()
        const res = (!forceCreate && this.currentSourceId)
          ? await updateScriptSource(this.currentSourceId, payload)
          : await createScriptSource(payload)
        if (res && res.code === 1) {
          const saved = (res && res.data) || {}
          const savedId = this.getScriptSourceId(saved) || this.currentSourceId
          await this.loadSources()
          await this.openSource(savedId, { updateRoute: options.updateRoute !== false })
          if (!options.silent) this.$message.success(this.text.saveSuccess)
          return this.currentSourceId
        }
        this.$message.error((res && res.msg) || this.text.saveFailed)
        return null
      } catch (e) {
        this.$message.error(e.backendMessage || e.message || this.text.saveFailed)
        return null
      } finally {
        this.savingScript = false
        this.savingScriptMode = ''
      }
    },
    async openPublishModal () {
      if (this.scriptCodeHidden) {
        this.$message.warning(this.text.hiddenScriptDesc)
        return
      }
      if (!await this.verifyScriptCode()) return
      const sourceId = await this.saveScript(false, { silent: true, loadingMode: 'publish' })
      if (!sourceId) return
      if (!await this.hasSuccessfulBacktest(sourceId)) {
        this.$message.warning(this.text.publishBacktestRequired)
        return
      }
      const meta = this.extractScriptMetadataFromCode(this.scriptCode)
      this.publishForm = {
        name: meta.name || this.deriveScriptName(),
        description: meta.description || (this.currentSource && this.currentSource.description) || ''
      }
      this.showPublishModal = true
    },
    async hasSuccessfulBacktest (sourceId) {
      const id = Number(sourceId || 0)
      if (!id) return false
      try {
        const res = await getStrategyBacktestHistory({
          assetType: 'script',
          assetId: id,
          status: 'success',
          limit: 1
        })
        const rows = Array.isArray(res && res.data) ? res.data : []
        return res && res.code === 1 && rows.length > 0
      } catch (_) {
        return false
      }
    },
    closePublishModal () {
      if (!this.publishingScript) this.showPublishModal = false
    },
    async confirmPublish () {
      const sourceId = this.currentSourceId || await this.saveScript(false, { silent: true, loadingMode: 'publish' })
      if (!sourceId) return
      this.publishingScript = true
      try {
        if (!await this.verifyScriptCode({ silentSuccess: true })) return
        const res = await publishScriptSource({
          sourceId,
          name: String(this.publishForm.name || '').trim() || this.deriveScriptName(),
          description: String(this.publishForm.description || '').trim()
        })
        if (res && res.code === 1) {
          this.$message.success(this.text.publishSuccess)
          this.showPublishModal = false
        } else {
          this.$message.error((res && res.msg) || this.text.publishFailed)
        }
      } catch (e) {
        this.$message.error(e.backendMessage || e.message || this.text.publishFailed)
      } finally {
        this.publishingScript = false
      }
    },
    deleteCurrentSource () {
      if (!this.currentSourceId) return
      this.$confirm({
        title: this.text.deleteConfirmTitle,
        content: this.text.deleteConfirmDesc,
        okType: 'danger',
        onOk: async () => {
          this.deletingScript = true
          try {
            const res = await deleteScriptSource(this.currentSourceId)
            if (res && res.code === 1) {
              this.$message.success(this.text.deleteSuccess)
              await this.loadSources()
              const firstId = this.scriptOptions.length ? this.scriptOptions[0].id : ''
              if (firstId) {
                await this.openSource(firstId, { updateRoute: true })
              } else {
                this.createNewDraft({ openTemplate: false })
              }
            } else {
              this.$message.error((res && res.msg) || this.text.deleteFailed)
            }
          } catch (e) {
            this.$message.error(e.backendMessage || e.message || this.text.deleteFailed)
          } finally {
            this.deletingScript = false
          }
        }
      })
    },
    openBacktestCenter () {
      const go = async () => {
        const sourceId = await this.saveScript(false, {
          skipUnchanged: true,
          silent: true,
          loadingMode: 'backtest',
          updateRoute: false
        })
        if (!sourceId) return
        this.$router.push({
          path: '/backtest-center',
          query: {
            assetType: this.currentAssetType,
            sourceId: String(sourceId)
          }
        }).catch(() => {})
      }
      go()
    },
    openVersionDrawer () {
      if (!this.currentSourceId) return
      if (this.scriptCodeHidden) {
        this.$message.info(this.text.versionHiddenBlocked)
        return
      }
      this.showVersionDrawer = true
      this.scriptVersionPreview = null
      this.loadScriptVersions()
    },
    async loadScriptVersions () {
      if (!this.currentSourceId) return
      this.scriptVersionLoading = true
      try {
        const res = await getScriptSourceVersions(this.currentSourceId)
        if (res && res.code === 1) {
          this.scriptVersions = Array.isArray(res.data) ? res.data : []
        } else {
          this.$message.error((res && res.msg) || this.text.versionLoadFailed)
        }
      } catch (e) {
        this.$message.error(e.backendMessage || e.message || this.text.versionLoadFailed)
      } finally {
        this.scriptVersionLoading = false
      }
    },
    async previewScriptVersion (item) {
      if (!item || !item.id) return
      if (this.scriptCodeHidden) {
        this.$message.info(this.text.versionHiddenBlocked)
        return
      }
      try {
        const res = await getScriptSourceVersion(item.id)
        if (res && res.code === 1) {
          this.scriptVersionPreview = res.data || null
        } else {
          this.$message.error((res && res.msg) || this.text.versionLoadFailed)
        }
      } catch (e) {
        this.$message.error(e.backendMessage || e.message || this.text.versionLoadFailed)
      }
    },
    confirmRestoreScriptVersion (item) {
      if (!item || !item.id) return
      if (this.scriptCodeHidden || item.restore_disabled) {
        this.$message.info(this.text.versionHiddenBlocked)
        return
      }
      this.$confirm({
        title: this.text.versionRestoreTitle,
        content: this.text.versionRestoreContent.replace('{version}', item.version_no),
        okText: this.text.versionRestore,
        cancelText: this.text.cancel,
        onOk: () => this.restoreScriptVersion(item)
      })
    },
    async restoreScriptVersion (item) {
      if (!item || !item.id) return
      if (this.scriptCodeHidden || item.restore_disabled) {
        this.$message.info(this.text.versionHiddenBlocked)
        return
      }
      this.restoringScriptVersionId = item.id
      try {
        const res = await restoreScriptSourceVersion(item.id)
        if (res && res.code === 1 && res.data) {
          this.applySource(res.data)
          await this.loadSources()
          await this.loadScriptVersions()
          this.scriptVersionPreview = null
          this.$message.success(this.text.versionRestored)
        } else {
          this.$message.error((res && res.msg) || this.text.versionRestoreFailed)
        }
      } catch (e) {
        this.$message.error(e.backendMessage || e.message || this.text.versionRestoreFailed)
      } finally {
        this.restoringScriptVersionId = null
      }
    },
    async openIndicatorConvertPicker () {
      this.indicatorConvertContext = null
      this.selectedIndicatorConvertId = undefined
      this.indicatorConvertInstruction = ''
      this.indicatorConvertError = ''
      this.showIndicatorConvertModal = true
      await this.loadIndicatorOptions()
    },
    async loadIndicatorOptions () {
      this.indicatorConvertIndicatorLoading = true
      try {
        const res = await getIndicatorListForStrategy()
        const list = this.extractIndicatorList(res)
          .map(item => this.normalizeIndicator(item))
          .filter(Boolean)
        this.indicatorConvertIndicators = list
      } catch (e) {
        this.indicatorConvertIndicators = []
        this.indicatorConvertError = e.backendMessage || e.message || this.text.indicatorConvertFailed
      } finally {
        this.indicatorConvertIndicatorLoading = false
      }
    },
    extractIndicatorList (res) {
      const data = res && res.data
      if (Array.isArray(data)) return data
      return []
    },
    normalizeIndicator (raw) {
      if (!raw || typeof raw !== 'object') return null
      return {
        indicatorId: String(raw.indicatorId || raw.id || '').trim(),
        name: String(raw.name || this.defaultIndicatorNameFromCode(raw.code || '') || '').trim(),
        description: String(raw.description || '').trim(),
        code: String(raw.code || '').trim(),
        params: raw.params || {},
        market: String(raw.market || '').trim(),
        symbol: String(raw.symbol || '').trim(),
        exchange_id: String(raw.exchange_id || '').trim(),
        market_type: String(raw.market_type || '').trim(),
        instrument_id: String(raw.instrument_id || '').trim(),
        timeframe: String(raw.timeframe || '').trim(),
        codeHidden: false
      }
    },
    defaultIndicatorNameFromCode (code) {
      const match = String(code || '').match(/^\s*my_indicator_name\s*=\s*(['"])(.*?)\1\s*$/m)
      return match ? match[2] : ''
    },
    handleIndicatorConvertSelect (id) {
      const target = (this.indicatorConvertIndicators || []).find(item => String(item.indicatorId) === String(id))
      this.indicatorConvertContext = target || null
      this.indicatorConvertError = ''
    },
    resolveIndicatorConversionContext (ctx = {}) {
      const query = (this.$route && this.$route.query) || {}
      return resolveIndicatorStrategyContext(ctx, query, this.runConfig || {})
    },
    buildIndicatorConversionPrompt () {
      const ctx = this.indicatorConvertContext || {}
      const source = this.resolveIndicatorConversionContext(ctx)
      const params = ctx.params && Object.keys(ctx.params).length ? JSON.stringify(ctx.params, null, 2) : '{}'
      const instruction = String(this.indicatorConvertInstruction || '').trim() ||
        'Convert the visible indicator signals into a conservative, event-based strategy. Confirm signals on closed bars and execute on the next bar to avoid look-ahead bias.'
      return [
        'Convert this QuantDinger chart-only indicator into executable QuantDinger Strategy API V2 Python code.',
        '',
        'Hard boundaries:',
        '- Return Strategy API V2 code only, using the current manifest and handler contract.',
        '- Start with a metadata docstring, then define initialize(context) and handle_data(context, data), scheduled callbacks, or on_rebalance(context, data).',
        '- The strategy source owns its universe, markets, subscriptions, frequency, factors, schedules, direction, sizing, entries, exits, and risk rules.',
        '- Preserve the source instrument and timeframe below in context.set_universe(...) and context.subscribe(...). Never replace them with USStock:SPY or another fallback instrument.',
        '- In initialize(context), call context.set_universe(...) and context.subscribe(frequency=...). Use context.set_warmup(...) when indicators need history.',
        '- Backtest and deployment panels only provide initial capital, date range, and optional leverage for a Crypto @swap strategy that explicitly calls context.allow_leverage(max_leverage=N).',
        '- Preserve the indicator signal logic first. Map visual buy/entry markers to long entries, sell/exit markers to long exits, and warning markers to wait/risk states.',
        '- Default to long-only unless the user explicitly asks for shorts and the indicator has clear bearish short-entry logic.',
        '- First classify every marker as long entry, long exit, short entry, short exit, warning/wait, or visual-only. Marker color and type="sell" alone do not prove short-entry intent.',
        '- Preserve composite event algebra exactly. For edge(A | B), compare the complete previous composite A_prev | B_prev; do not emit a duplicate event on the next bar.',
        '- If the user explicitly requests symmetric shorts from a long-only indicator, derive and label them as new behavior; otherwise do not invent short entries.',
        '- Confirm indicator conditions on completed bars. Orders from handle_data are filled by the engine on the next available bar open.',
        '- Use get_history, indicator, factor, get_factors, and get_fundamentals without future data. TA-Lib functions are available through indicator/factor.',
        '- Use data.current(symbol, field) for current scalar values. There is no get_current_data API. get_position(symbol) returns a Position with amount, avg_cost, and last_price; it has no quantity or cost_basis.',
        '- Fundamental factors are point-in-time and portfolio-oriented; never invent fundamental values or backfill future observations.',
        '- Use order, order_value, order_target, order_target_value, and order_target_percent. Prevent duplicate intents on the same bar.',
        '- Declare tunable strategy knobs with # @param and read matching context.params defaults only inside handlers or callbacks, never inside initialize(context).',
        '- For risk-managed entries, attach explicit protection rules to entries with stop_loss_pct, take_profit_pct, trailing_stop_pct, or time_limit_seconds.',
        '- Remove display-only parameters such as colors, visibility toggles, marker offsets, line extension, and plot layout.',
        '- Do not generate grid, DCA, or martingale logic unless the user explicitly requests a Strategy API V2 robot.',
        '',
        `Indicator name: ${ctx.name || this.text.defaultIndicatorName}`,
        ctx.description ? `Indicator description: ${ctx.description}` : '',
        source.instrument ? `Source instrument: ${source.instrument}` : '',
        source.timeframe ? `Source timeframe: ${source.timeframe}` : '',
        `Indicator params JSON:\n${params}`,
        '',
        `User conversion request:\n${instruction}`,
        '',
        `Indicator source code:\n\`\`\`python\n${ctx.code || ''}\n\`\`\``
      ].filter(Boolean).join('\n')
    },
    async confirmIndicatorToStrategy () {
      const ctx = this.indicatorConvertContext || {}
      if (!ctx.indicatorId) {
        this.indicatorConvertError = this.text.indicatorConvertSelectFirst
        return
      }
      if (ctx.codeHidden || !ctx.code) {
        this.indicatorConvertError = ctx.codeHidden ? this.text.indicatorConvertHiddenBlocked : this.text.indicatorConvertNoCode
        return
      }
      this.indicatorConvertLoading = true
      this.indicatorConvertError = ''
      try {
        const res = await aiGenerateStrategy({
          prompt: this.buildIndicatorConversionPrompt()
        })
        const code = this.extractAiGeneratedCode(res)
        if (!code) throw new Error((res && res.msg) || this.text.indicatorConvertFailed)
        const created = await createScriptSource({
          name: this.extractScriptMetadataFromCode(code).name || `${ctx.name || this.text.defaultIndicatorName} Strategy`,
          description: this.extractScriptMetadataFromCode(code).description || `AI converted from indicator: ${ctx.name || this.text.defaultIndicatorName}`,
          code,
          metadata: this.buildGeneratedMetadata(ctx)
        })
        if (!(created && created.code === 1)) throw new Error((created && created.msg) || this.text.indicatorConvertFailed)
        await this.loadSources()
        const sourceId = this.getScriptSourceId(created.data)
        await this.openSource(sourceId, { updateRoute: false })
        this.finishIndicatorConversion(sourceId)
        this.$message.success(this.text.indicatorConvertSuccess)
      } catch (e) {
        this.indicatorConvertError = e.backendMessage || e.message || this.text.indicatorConvertFailed
      } finally {
        this.indicatorConvertLoading = false
      }
    },
    extractAiGeneratedCode (res) {
      if (!res || typeof res !== 'object') return ''
      const data = res.data || {}
      const candidates = [res.code, data.code]
      const code = candidates.find(item => typeof item === 'string' && item.trim())
      return code ? String(code).trim() : ''
    },
    buildGeneratedMetadata (ctx = {}) {
      const source = this.resolveIndicatorConversionContext(ctx)
      const lastRunConfig = {
        ...this.buildTradingConfig(),
        market_category: source.market || this.runConfig.market_category,
        symbol: source.symbol || this.runConfig.symbol,
        timeframe: source.timeframe || this.runConfig.timeframe,
        exchange_id: source.market.toLowerCase() === 'crypto' ? source.exchangeId : '',
        market_type: source.marketType
      }
      return {
        generated_by: 'ai_indicator_to_strategy',
        source_indicator_id: ctx.indicatorId || '',
        source_indicator_name: ctx.name || '',
        source_indicator_market: source.market,
        source_indicator_symbol: source.symbol,
        source_indicator_instrument: source.instrument,
        source_indicator_timeframe: source.timeframe,
        lifecycle_verified: false,
        script_verified: false,
        last_run_config: lastRunConfig,
        script_template_params: {}
      }
    },
    closeIndicatorConvertModal () {
      if (this.indicatorConvertLoading) return
      this.showIndicatorConvertModal = false
      this.indicatorConvertError = ''
      this.clearIndicatorConvertSession()
      this.clearIndicatorConvertRoute()
    },
    finishIndicatorConversion (sourceId) {
      this.showIndicatorConvertModal = false
      this.indicatorConvertError = ''
      this.clearIndicatorConvertSession()
      this.writeRouteSource(sourceId)
    },
    clearIndicatorConvertSession () {
      const key = String((this.$route.query || {}).convert_key || '').trim()
      if (!key || typeof sessionStorage === 'undefined') return
      try {
        sessionStorage.removeItem(key)
      } catch (_) {}
    },
    async applyIndicatorConvertRouteOnce () {
      const query = this.$route.query || {}
      if (!this.isIndicatorConvertRoute()) return
      let context = null
      const key = String(query.convert_key || '').trim()
      if (key && typeof sessionStorage !== 'undefined') {
        try {
          context = JSON.parse(sessionStorage.getItem(key) || 'null')
        } catch (_) {
          context = null
        }
      }
      if (!(this.indicatorConvertIndicators || []).length) {
        await this.loadIndicatorOptions()
      }
      if (context) {
        const storedContext = this.normalizeIndicator(context)
        if (storedContext) {
          const sourceIndex = (this.indicatorConvertIndicators || []).findIndex(item => String(item.indicatorId) === storedContext.indicatorId)
          if (sourceIndex >= 0) {
            const mergedContext = {
              ...this.indicatorConvertIndicators[sourceIndex],
              ...storedContext
            }
            this.indicatorConvertIndicators.splice(sourceIndex, 1, mergedContext)
            context = mergedContext
          } else {
            this.indicatorConvertIndicators.unshift(storedContext)
            context = storedContext
          }
        }
      } else if (query.source_indicator_id || query.indicator_id) {
        context = (this.indicatorConvertIndicators || []).find(item => String(item.indicatorId) === String(query.source_indicator_id || query.indicator_id))
      }
      if (!context) return
      this.indicatorConvertContext = context
      this.selectedIndicatorConvertId = context.indicatorId ? String(context.indicatorId) : undefined
      this.showIndicatorConvertModal = true
    },
    clearIndicatorConvertRoute () {
      const query = { ...(this.$route.query || {}) }
      delete query.convert
      delete query.convert_key
      delete query.source_indicator_id
      delete query.indicator_id
      delete query.indicatorId
      delete query.market
      delete query.symbol
      delete query.timeframe
      this.replaceRouteQuery(query)
    },
    marketLabel (market) {
      const text = String(market || '').trim()
      if (!text) return '-'
      const key = `dashboard.indicator.market.${text}`
      const translated = this.$t(key)
      return translated && translated !== key ? translated : text
    },
    formatTime (value) {
      if (!value) return ''
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return String(value)
      return date.toLocaleString()
    }
  }
}
</script>

<style lang="less" scoped>
.strategy-ide-shell {
  box-sizing: border-box;
  height: calc(100vh - 64px);
  padding: 12px;
  background: #f5f7fb;
  overflow: hidden;
}

.strategy-ide-layout {
  height: 100%;
  min-height: 0;
}

.script-panel {
  height: 100%;
  min-height: 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.script-panel ::v-deep .strategy-editor {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.script-panel ::v-deep .editor-top-toolbar {
  flex: 0 0 auto;
}

.script-panel ::v-deep .editor-layout {
  flex: 1 1 auto;
  height: calc(100% - 57px);
  min-height: 0;
}

.script-panel ::v-deep .code-col,
.script-panel ::v-deep .side-col {
  height: 100%;
  min-height: 0;
}

.script-panel ::v-deep .code-section,
.script-panel ::v-deep .side-tabs {
  height: 100%;
  min-height: 0;
}

.script-panel ::v-deep .code-editor-container {
  min-height: 0;
}

.script-panel ::v-deep .CodeMirror {
  height: 100% !important;
}

.ide-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.toolbar-left {
  flex: 1 1 auto;
}

.toolbar-right {
  flex: 0 0 auto;
}

.strategy-workspace-switcher {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 10px;
  border-right: 1px solid #e5e7eb;
}

.strategy-workspace-copy {
  display: flex;
  width: 150px;
  min-width: 0;
  flex-direction: column;
  line-height: 1.25;
}

.strategy-workspace-copy strong {
  color: #202735;
  font-size: 13px;
}

.strategy-workspace-copy span {
  margin-top: 3px;
  overflow: hidden;
  color: #7b8494;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.strategy-workspace-switcher .ant-radio-button-wrapper {
  height: 36px;
  padding: 0 13px;
  line-height: 34px;
  font-weight: 700;
}

.script-select-label {
  flex: 0 0 auto;
  color: #6b7280;
  font-size: 13px;
  font-weight: 600;
}

.script-select {
  width: 280px;
}

.ide-icon-btn {
  width: 36px;
  height: 36px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ide-icon-btn--danger {
  color: #ff4d4f;
  border-color: rgba(255, 77, 79, 0.45);
}

.script-save-button,
.script-live-button,
.script-backtest-button,
.indicator-convert-button,
.factor-library-button,
.universe-library-button {
  height: 36px;
  font-weight: 700;
}

.script-save-button,
.script-live-button {
  min-width: 76px;
}

.script-backtest-button,
.indicator-convert-button {
  min-width: 120px;
}

.universe-library-button--selected {
  border-color: var(--primary-color, #52c41a);
  color: var(--primary-color, #52c41a);
  background: rgba(82, 196, 26, 0.08);
}

.theme-dark {
  background: #0f0f0f;

  .script-panel {
    border-color: rgba(255, 255, 255, 0.1);
    background: #141414;
  }

  .ide-toolbar {
    border-bottom-color: rgba(255, 255, 255, 0.08);
    background: #141414;
  }

  .script-select-label {
    color: rgba(255, 255, 255, 0.62);
  }

  .strategy-workspace-copy strong {
    color: rgba(255, 255, 255, 0.9);
  }

  .strategy-workspace-copy span {
    color: rgba(255, 255, 255, 0.46);
  }

  .strategy-workspace-switcher {
    border-right-color: rgba(255, 255, 255, 0.1);
  }

  .strategy-workspace-switcher .ant-radio-button-wrapper {
    border-color: rgba(255, 255, 255, 0.12);
    color: rgba(255, 255, 255, 0.68);
    background: #202020;
  }

  .strategy-workspace-switcher .ant-radio-button-wrapper-checked {
    border-color: var(--primary-color, #52c41a);
    color: #fff;
    background: var(--primary-color, #52c41a);
  }

  ::v-deep .ant-select-selection,
  ::v-deep .ant-input,
  ::v-deep textarea.ant-input,
  ::v-deep .ant-input-number,
  ::v-deep .ant-input-number-input {
    background: #111 !important;
    border-color: rgba(255, 255, 255, 0.12) !important;
    color: rgba(255, 255, 255, 0.86) !important;
  }
}

@media (max-width: 1180px) {
  .ide-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-left,
  .toolbar-right {
    width: 100%;
    flex-wrap: wrap;
  }

  .script-select {
    flex: 1 1 260px;
    width: auto;
  }
}
</style>

<style lang="less">
.robot-builder-drawer {
  .ant-drawer-content-wrapper {
    max-width: 96vw;
  }

  .ant-drawer-body {
    height: calc(100vh - 55px);
    display: flex;
    overflow: hidden;
    padding: 14px 18px 18px;
    background: #f4f6f8;
    flex-direction: column;
  }

  .robot-builder-intro {
    flex: 0 0 auto;
    margin-bottom: 12px;
    padding: 10px 12px;
    border: 1px solid #d9e2ec;
    border-radius: 8px;
    background: #fff;
    color: #52606d;
  }

  .executor-page {
    min-height: 0;
    flex: 1;
  }
}

.robot-builder-drawer--dark {
  .ant-drawer-header,
  .ant-drawer-content,
  .ant-drawer-body {
    border-color: #2b2b2b;
    background: #0b0b0b;
    color: rgba(255, 255, 255, 0.86);
  }

  .ant-drawer-title,
  .ant-drawer-close {
    color: rgba(255, 255, 255, 0.86);
  }

  .robot-builder-intro {
    border-color: #2b2b2b;
    background: #151515;
    color: rgba(255, 255, 255, 0.58);
  }
}

.script-publish-modal {
  .ant-modal-content {
    overflow: hidden;
    border-radius: 12px;
  }

  .ant-modal-header {
    padding: 18px 24px;
    border-bottom: 1px solid #edf0f5;
  }

  .ant-modal-body {
    padding: 18px 24px 20px;
    background: #f6f7f9;
  }

  .ant-modal-footer {
    padding: 14px 24px;
    border-top: 1px solid #edf0f5;
    background: #fff;
  }

  .publish-form {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .publish-summary-card {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 74px;
    padding: 14px;
    border: 1px solid rgba(255, 77, 79, 0.22);
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(255, 77, 79, 0.1) 0%, #fff 72%);
  }

  .publish-summary-icon {
    width: 42px;
    height: 42px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: #fff;
    background: var(--primary-color, #ff4d4f);
    box-shadow: 0 10px 24px rgba(255, 77, 79, 0.24);
    font-size: 18px;
  }

  .publish-summary-main {
    flex: 1;
    min-width: 0;
  }

  .publish-summary-label {
    margin-bottom: 3px;
    font-size: 12px;
    font-weight: 700;
    color: #6b7280;
  }

  .publish-summary-name {
    overflow: hidden;
    color: #111827;
    font-size: 16px;
    font-weight: 800;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .publish-summary-tag {
    margin: 0;
    height: 24px;
    line-height: 22px;
    border-radius: 999px;
    font-weight: 700;
  }

  .publish-note {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    padding: 10px 12px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    color: #4b5563;
    font-size: 13px;
    line-height: 1.55;
  }

  .publish-note .anticon {
    margin-top: 3px;
    color: var(--primary-color, #ff4d4f);
  }

  .publish-section,
  .publish-option-card {
    padding: 14px;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    background: #fff;
  }

  .publish-section-title,
  .field-label,
  .publish-option-head {
    color: #1f2937;
    font-size: 13px;
    font-weight: 800;
  }

  .publish-section-title {
    margin-bottom: 10px;
  }

  .publish-pricing-group {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    width: 100%;
  }

  .publish-pricing-group .ant-radio-button-wrapper {
    height: 40px;
    line-height: 38px;
    padding: 0 14px;
    border: 1px solid #dfe3ea;
    border-radius: 8px !important;
    color: #4b5563;
    text-align: center;
    font-weight: 700;
    background: #fafafa;
    box-shadow: none;
  }

  .publish-pricing-group .ant-radio-button-wrapper::before {
    display: none;
  }

  .publish-pricing-group .ant-radio-button-wrapper-checked {
    color: #fff;
    border-color: var(--primary-color, #ff4d4f);
    background: var(--primary-color, #ff4d4f);
    box-shadow: 0 8px 18px rgba(255, 77, 79, 0.24);
  }

  .publish-price-box {
    margin-top: 12px;
  }

  .publish-price-input {
    width: 100%;
  }

  .publish-option-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .publish-option-card.active {
    border-color: var(--primary-color, #ff4d4f);
    background: linear-gradient(135deg, rgba(255, 77, 79, 0.08) 0%, #fff 76%);
    box-shadow: inset 0 0 0 1px rgba(255, 77, 79, 0.14);
  }

  .publish-option-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 8px;
  }

  .publish-hint {
    color: #6b7280;
    font-size: 12px;
    line-height: 1.55;
  }
}

.indicator-convert-modal {
  .indicator-convert-box {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .indicator-convert-selector {
    padding: 12px;
    border: 1px solid rgba(239, 68, 68, 0.18);
    border-radius: 8px;
    background: rgba(239, 68, 68, 0.06);
  }

  .field-label {
    display: block;
    color: #334155;
    font-size: 13px;
    font-weight: 700;
  }

  .field-label--spaced {
    margin-top: 4px;
  }

  .indicator-convert-current {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 14px 16px;
    border: 1px solid rgba(239, 68, 68, 0.18);
    border-radius: 8px;
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(255, 255, 255, 0.96));
  }

  .indicator-convert-current span {
    display: block;
    margin-bottom: 4px;
    color: #64748b;
    font-size: 12px;
    font-weight: 700;
  }

  .indicator-convert-current strong {
    color: #111827;
    font-size: 16px;
    font-weight: 800;
  }

  .indicator-convert-current small {
    color: #64748b;
    font-size: 12px;
    white-space: nowrap;
  }

  .indicator-convert-note {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    padding: 10px 12px;
    border: 1px solid rgba(59, 130, 246, 0.16);
    border-radius: 6px;
    background: rgba(59, 130, 246, 0.06);
    color: #475569;
    font-size: 13px;
    line-height: 1.55;
  }

  .indicator-convert-note .anticon {
    margin-top: 3px;
    color: #2563eb;
  }
}

.code-version-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.code-version-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.code-version-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.code-version-item__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.code-version-item__main strong {
  color: #111827;
}

.code-version-item__main span,
.code-version-item__main small {
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.code-version-item__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.code-version-preview {
  margin-top: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.code-version-preview__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
}

.code-version-preview pre {
  max-height: 360px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.6;
}

.code-version-hidden {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 20px;
  text-align: center;
  color: #64748b;
  background: #0f172a;
}

.code-version-hidden .anticon {
  color: #52c41a;
  font-size: 24px;
}

.code-version-hidden strong {
  color: #e2e8f0;
}

.script-publish-modal--dark,
.indicator-convert-modal--dark,
.script-version-drawer--dark {
  .ant-modal-content,
  .ant-modal-header,
  .ant-modal-footer,
  .ant-drawer-content,
  .ant-drawer-header {
    background: #181818;
    border-color: rgba(255, 255, 255, 0.08);
  }

  .ant-modal-body {
    background: #141414;
  }

  .ant-modal-title,
  .ant-modal-close,
  .ant-drawer-title,
  .ant-drawer-close,
  .publish-section-title,
  .publish-option-head,
  .field-label,
  .code-version-item__main strong {
    color: rgba(255, 255, 255, 0.88);
  }

  .publish-summary-card,
  .indicator-convert-current {
    border-color: rgba(255, 77, 79, 0.32);
    background: linear-gradient(135deg, rgba(255, 77, 79, 0.18) 0%, #1c1c1c 72%);
  }

  .publish-summary-name,
  .indicator-convert-current strong {
    color: rgba(255, 255, 255, 0.9);
  }

  .publish-summary-label,
  .publish-hint,
  .indicator-convert-current span,
  .indicator-convert-current small,
  .code-version-toolbar,
  .code-version-item__main span,
  .code-version-item__main small {
    color: rgba(255, 255, 255, 0.52);
  }

  .publish-note,
  .publish-section,
  .publish-option-card,
  .indicator-convert-selector,
  .indicator-convert-note,
  .code-version-item,
  .code-version-preview {
    border-color: rgba(255, 255, 255, 0.1);
    background: #1f1f1f;
  }

  .publish-option-card.active {
    border-color: var(--primary-color, #ff4d4f);
    background: linear-gradient(135deg, rgba(255, 77, 79, 0.16) 0%, #1f1f1f 78%);
  }

  .code-version-preview__head {
    border-color: rgba(255, 255, 255, 0.08);
    background: #141414;
  }
}
</style>
