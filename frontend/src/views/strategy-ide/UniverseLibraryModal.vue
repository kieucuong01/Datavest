<template>
  <a-modal
    :visible="visible"
    :title="$t('universeLibrary.title')"
    :width="1080"
    :footer="null"
    :destroy-on-close="false"
    :wrap-class-name="isDark ? 'universe-library-modal universe-library-modal--dark' : 'universe-library-modal'"
    @cancel="$emit('close')"
  >
    <div class="universe-library-intro">
      <div>
        <strong>{{ $t('universeLibrary.subtitle') }}</strong>
        <span>{{ $t('universeLibrary.description') }}</span>
      </div>
      <a-button class="universe-create-button" icon="plus" @click="openCreate">{{ $t('universeManager.create') }}</a-button>
    </div>

    <a-alert
      class="universe-library-alert"
      type="info"
      show-icon
      :message="$t(assetType === 'portfolio_strategy' ? 'universeLibrary.portfolioNotice' : 'universeLibrary.ctaNotice')"
    />

    <div class="universe-library-tools">
      <a-input
        v-model="search"
        allow-clear
        :aria-label="$t('universeManager.search')"
        :placeholder="$t('universeManager.search')"
      >
        <a-icon slot="prefix" type="search" />
      </a-input>
      <a-radio-group v-model="scopeFilter" button-style="solid">
        <a-radio-button value="all">{{ $t('factorLibrary.all') }}</a-radio-button>
        <a-radio-button value="system">{{ $t('universeManager.tabs.system') }}</a-radio-button>
        <a-radio-button value="personal">{{ $t('universeManager.tabs.personal') }}</a-radio-button>
        <a-radio-button value="watchlist">{{ $t('universeManager.tabs.watchlist') }}</a-radio-button>
      </a-radio-group>
      <a-select
        v-model="marketFilter"
        :dropdown-class-name="isDark ? 'universe-library-dropdown universe-library-dropdown--dark' : 'universe-library-dropdown'"
      >
        <a-select-option value="all">{{ $t('universeManager.allMarkets') }}</a-select-option>
        <a-select-option v-for="market in markets" :key="market" :value="market">{{ marketLabel(market) }}</a-select-option>
      </a-select>
      <a-button icon="reload" :loading="loading" @click="loadUniverses()">{{ $t('universeManager.reload') }}</a-button>
    </div>

    <a-spin :spinning="loading">
      <div class="universe-library-workspace">
        <div class="universe-library-list">
          <button
            v-for="item in filteredUniverses"
            :key="item.id"
            type="button"
            class="universe-card"
            :class="{ 'universe-card--active': selected && Number(selected.id) === Number(item.id) }"
            :aria-pressed="selected && Number(selected.id) === Number(item.id)"
            @click="selectUniverse(item)"
          >
            <span class="universe-card__head">
              <span class="universe-card__name">{{ universeLabel(item) }}</span>
              <a-tag :color="item.code === 'watchlist' ? 'gold' : item.is_system ? 'blue' : 'green'">{{ scopeLabel(item) }}</a-tag>
            </span>
            <span class="universe-card__code">{{ item.code }}</span>
            <span class="universe-card__stats">
              <span>{{ marketLabel(item.market) }}</span>
              <strong>{{ Number(item.member_count || 0).toLocaleString() }} {{ $t('universeManager.symbols') }}</strong>
            </span>
            <span v-if="Number(selectedUniverseId) === Number(item.id)" class="universe-card__selected">
              <a-icon type="check-circle" /> {{ $t('universeLibrary.currentSelection') }}
            </span>
          </button>
          <a-empty v-if="!filteredUniverses.length" :description="$t('universeManager.empty')" />
        </div>

        <div v-if="selected" class="universe-detail">
          <div class="universe-detail__heading">
            <div>
              <span class="universe-detail__eyebrow">{{ selected.code }}</span>
              <h3>{{ universeLabel(selected) }}</h3>
              <p>{{ marketLabel(selected.market) }} · {{ scopeLabel(selected) }} · {{ Number(selected.member_count || 0).toLocaleString() }} {{ $t('universeManager.symbols') }}</p>
            </div>
            <div class="universe-detail__actions">
              <a-button
                type="primary"
                icon="check"
                class="universe-apply-button"
                :disabled="assetType !== 'portfolio_strategy'"
                @click="useUniverse(selected)"
              >
                {{ Number(selectedUniverseId) === Number(selected.id) ? $t('universeLibrary.selected') : $t('universeLibrary.use') }}
              </a-button>
            </div>
          </div>

          <div class="universe-detail__facts">
            <div><span>{{ $t('universeManager.market') }}</span><strong>{{ marketLabel(selected.market) }}</strong></div>
            <div><span>{{ $t('universeManager.members') }}</span><strong>{{ Number(selected.member_count || 0).toLocaleString() }}</strong></div>
            <div><span>{{ $t('universeManager.version') }}</span><strong>{{ universeVersion(selected) }}</strong></div>
            <div><span>{{ $t('universeManager.status.active') }}</span><strong>{{ $t(`universeManager.status.${selected.status || 'data_required'}`) }}</strong></div>
          </div>

          <section class="universe-detail__section">
            <div class="universe-detail__section-head">
              <div>
                <h4>{{ $t('universeLibrary.codeReference') }}</h4>
                <p>{{ $t('universeLibrary.codeReferenceHint') }}</p>
              </div>
              <a-button size="small" icon="copy" @click="copyReference(selected)">{{ $t('universeLibrary.copyReference') }}</a-button>
            </div>
            <pre>{{ referenceLine(selected) }}</pre>
          </section>

          <section class="universe-detail__section universe-detail__members">
            <div class="universe-detail__section-head">
              <h4>{{ $t('universeManager.viewMembers') }}</h4>
              <a-tag>{{ members.length }} {{ $t('universeManager.symbols') }}</a-tag>
            </div>
            <a-spin :spinning="membersLoading">
              <div v-if="members.length" class="universe-member-table-wrap">
                <table class="universe-member-table">
                  <thead><tr><th>{{ $t('universeManager.symbol') }}</th><th>{{ $t('universeManager.memberName') }}</th><th>{{ $t('universeManager.market') }}</th><th>{{ $t('universeManager.weight') }}</th></tr></thead>
                  <tbody>
                    <tr v-for="member in members.slice(0, 100)" :key="`${member.market}:${member.symbol}`">
                      <td><code>{{ member.symbol }}</code></td>
                      <td>{{ member.name || '-' }}</td>
                      <td>{{ marketLabel(member.market) }}</td>
                      <td>{{ member.weight == null ? '-' : member.weight }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <a-empty v-else-if="!membersLoading" :description="$t('universeLibrary.noMembers')" />
            </a-spin>
          </section>
        </div>
        <a-empty v-else class="universe-detail-empty" :description="$t('universeLibrary.selectHint')" />
      </div>
    </a-spin>

    <a-modal
      :visible="showCreate"
      :title="$t('universeManager.create')"
      :confirm-loading="creating"
      :ok-button-props="{ props: { disabled: !canCreateUniverse } }"
      :ok-text="$t('universeManager.save')"
      :cancel-text="$t('universeManager.cancel')"
      :wrap-class-name="isDark ? 'universe-create-modal universe-create-modal--dark' : 'universe-create-modal'"
      @ok="createPersonalUniverse"
      @cancel="showCreate = false"
    >
      <a-form-item
        :label="$t('universeManager.name')"
        :validate-status="createTouched && !canCreateUniverse ? 'error' : ''"
        :help="createTouched && !canCreateUniverse ? $t('universeManager.nameRequired') : ''"
        required
      >
        <a-input
          id="universe-create-name"
          ref="createNameInput"
          v-model="createForm.name"
          aria-required="true"
          @input="createTouched = true"
        />
      </a-form-item>
      <label class="universe-create-label" for="universe-create-market">{{ $t('universeManager.market') }}</label>
      <a-select id="universe-create-market" v-model="createForm.market" class="universe-create-full">
        <a-select-option v-for="market in markets" :key="market" :value="market">{{ marketLabel(market) }}</a-select-option>
      </a-select>
      <label class="universe-create-label" for="universe-create-members">{{ $t('universeManager.members') }}</label>
      <a-textarea id="universe-create-members" v-model="createForm.members" :rows="8" :placeholder="createForm.market === 'Mixed' ? $t('universeManager.mixedPlaceholder') : $t('universeManager.placeholder')" />
      <small>{{ $t('universeManager.memberHint') }}</small>
    </a-modal>
  </a-modal>
</template>

<script>
import { createUniverse, getUniverseMembers, getUniverses } from '@/api/universe'
import { ACTIVE_MARKET_ORDER } from '@/utils/supportedMarkets'

export default {
  name: 'UniverseLibraryModal',
  props: {
    visible: { type: Boolean, default: false },
    isDark: { type: Boolean, default: false },
    assetType: { type: String, default: 'script' },
    selectedUniverseId: { type: [Number, String], default: undefined }
  },
  data () {
    return {
      loading: false,
      loaded: false,
      membersLoading: false,
      creating: false,
      universes: [],
      members: [],
      memberCache: Object.create(null),
      memberRequestId: 0,
      selected: null,
      search: '',
      scopeFilter: 'all',
      marketFilter: 'all',
      markets: [...ACTIVE_MARKET_ORDER, 'Mixed'],
      showCreate: false,
      createTouched: false,
      createForm: { name: '', market: 'VNStock', members: '' }
    }
  },
  computed: {
    filteredUniverses () {
      const query = String(this.search || '').trim().toLowerCase()
      return this.universes.filter(item => {
        if (this.scopeFilter === 'system' && (!item.is_system || item.code === 'watchlist')) return false
        if (this.scopeFilter === 'personal' && (item.is_system || item.code === 'watchlist')) return false
        if (this.scopeFilter === 'watchlist' && item.code !== 'watchlist') return false
        if (this.marketFilter !== 'all' && item.market !== this.marketFilter) return false
        return !query || `${this.universeLabel(item)} ${item.code} ${item.market}`.toLowerCase().includes(query)
      })
    },
    canCreateUniverse () {
      return Boolean(String(this.createForm.name || '').trim())
    }
  },
  watch: {
    visible (value) {
      if (!value) return
      if (this.loaded) this.ensureSelection()
      else this.loadUniverses()
    },
    selectedUniverseId () {
      if (this.visible) this.ensureSelection()
    },
    search () {
      this.ensureFilteredSelection()
    },
    scopeFilter () {
      this.ensureFilteredSelection()
    },
    marketFilter () {
      this.ensureFilteredSelection()
    }
  },
  methods: {
    unwrap (res) {
      return res && Object.prototype.hasOwnProperty.call(res, 'data') ? res.data : res
    },
    async loadUniverses (preferredId = undefined) {
      this.loading = true
      try {
        const payload = this.unwrap(await getUniverses())
        this.universes = Array.isArray(payload) ? payload : []
        this.memberCache = Object.create(null)
        this.loaded = true
        await this.ensureSelection(true, preferredId)
      } catch (error) {
        this.universes = []
        this.$message.error(error.backendMessage || error.message || this.$t('universeManager.loadFailed'))
      } finally {
        this.loading = false
      }
    },
    ensureFilteredSelection () {
      if (!this.visible || !this.loaded) return
      this.$nextTick(() => this.ensureSelection())
    },
    async ensureSelection (force = false, preferredId = this.selectedUniverseId) {
      const selectedId = this.selected && this.selected.id
      const preferred = this.filteredUniverses.find(item => Number(item.id) === Number(preferredId)) ||
        this.filteredUniverses.find(item => Number(item.id) === Number(selectedId)) ||
        this.filteredUniverses[0] || null
      if (!preferred) {
        this.selected = null
        this.members = []
        this.membersLoading = false
        return
      }
      if (!force && Number(selectedId) === Number(preferred.id) && (this.memberCache[String(preferred.id)] || this.membersLoading)) return
      await this.selectUniverse(preferred, force)
    },
    async selectUniverse (item, force = false) {
      this.selected = item
      const cacheKey = String(item.id)
      if (!force && this.memberCache[cacheKey]) {
        this.members = this.memberCache[cacheKey]
        this.membersLoading = false
        return
      }
      this.members = []
      this.membersLoading = true
      const requestId = ++this.memberRequestId
      try {
        const payload = this.unwrap(await getUniverseMembers(item.id)) || {}
        const nextMembers = Array.isArray(payload.members) ? payload.members : []
        this.$set(this.memberCache, cacheKey, nextMembers)
        if (requestId === this.memberRequestId && this.selected && Number(this.selected.id) === Number(item.id)) this.members = nextMembers
      } catch (error) {
        if (requestId === this.memberRequestId) this.$message.error(error.backendMessage || error.message || this.$t('universeManager.loadMembersFailed'))
      } finally {
        if (requestId === this.memberRequestId) this.membersLoading = false
      }
    },
    universeLabel (item) {
      const key = item && item.name_i18n_key
      const translated = key ? this.$t(key) : ''
      return translated && translated !== key ? translated : ((item && (item.name || item.code)) || '-')
    },
    marketLabel (market) {
      const key = `universeManager.market.${market || 'Mixed'}`
      const translated = this.$t(key)
      return translated && translated !== key ? translated : market
    },
    scopeLabel (item) {
      if (item.code === 'watchlist') return this.$t('universeManager.tabs.watchlist')
      return this.$t(item.is_system ? 'universeManager.tabs.system' : 'universeManager.tabs.personal')
    },
    universeVersion (item) {
      return (item.metadata && item.metadata.snapshot_as_of) || (item.updated_at ? String(item.updated_at).slice(0, 10) : '-')
    },
    referenceLine (item) {
      return `context.set_universe(pool="${String(item.code || '').trim()}")`
    },
    async copyReference (item) {
      const value = this.referenceLine(item)
      try {
        await navigator.clipboard.writeText(value)
        this.$message.success(this.$t('universeLibrary.copySuccess'))
      } catch (_) {
        this.$message.error(this.$t('factorLibrary.copyFailed'))
      }
    },
    useUniverse (item) {
      this.$emit('use', { ...item, name: this.universeLabel(item) })
    },
    openCreate () {
      this.createForm = { name: '', market: 'VNStock', members: '' }
      this.createTouched = false
      this.showCreate = true
      this.$nextTick(() => {
        if (this.$refs.createNameInput && this.$refs.createNameInput.focus) this.$refs.createNameInput.focus()
      })
    },
    parseMembers () {
      return String(this.createForm.members || '').split(/\r?\n/).map(value => value.trim()).filter(Boolean).map(value => {
        if (this.createForm.market !== 'Mixed') return { market: this.createForm.market, symbol: value }
        const separator = value.indexOf(':')
        if (separator <= 0) throw new Error(this.$t('universeManager.mixedFormatError'))
        return { market: value.slice(0, separator).trim(), symbol: value.slice(separator + 1).trim() }
      })
    },
    async createPersonalUniverse () {
      this.createTouched = true
      if (!String(this.createForm.name || '').trim()) return
      this.creating = true
      try {
        const created = this.unwrap(await createUniverse({
          name: this.createForm.name.trim(),
          market: this.createForm.market,
          universeType: 'manual',
          members: this.parseMembers()
        }))
        this.showCreate = false
        this.search = ''
        this.scopeFilter = 'personal'
        this.marketFilter = 'all'
        await this.loadUniverses(created && created.id)
        this.$message.success(this.$t('universeManager.saved'))
      } catch (error) {
        this.$message.error(error.backendMessage || error.message || this.$t('universeManager.saveFailed'))
      } finally {
        this.creating = false
      }
    }
  }
}
</script>

<style lang="less">
.universe-library-modal {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;

  .ant-modal { top: 32px; padding-bottom: 32px; }
  .ant-modal-body { padding: 20px 24px 24px; overflow: hidden; }
}
.universe-library-intro,.universe-library-tools,.universe-detail__heading,.universe-detail__section-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.universe-library-intro{margin-bottom:14px;padding:14px 16px;border:1px solid #e6e9ef;border-radius:10px;background:#fafbfc}.universe-library-intro>.ant-btn{display:inline-flex;height:34px;align-items:center;justify-content:center;line-height:1;white-space:nowrap}.universe-library-intro strong,.universe-library-intro span{display:block}.universe-library-intro strong{margin-bottom:4px;color:#172033;font-size:15px}.universe-library-intro span{color:#6b7280;font-size:13px}.universe-library-alert{margin-bottom:14px}.universe-library-tools{margin-bottom:14px;justify-content:flex-start}.universe-library-tools .ant-input-affix-wrapper{width:270px}.universe-library-tools>.ant-select{width:150px}.universe-library-workspace{display:grid;grid-template-columns:360px minmax(0,1fr);height:min(620px,calc(100vh - 292px));min-height:390px;overflow:hidden;border:1px solid #e6e9ef;border-radius:10px}.universe-library-list{min-height:0;padding:12px;overflow-y:auto;overscroll-behavior:contain;border-right:1px solid #e6e9ef;background:#f7f8fa}.universe-card{display:block;width:100%;margin:0 0 9px;padding:12px;border:1px solid #e2e6ec;border-radius:8px;color:inherit;text-align:left;background:#fff;cursor:pointer}.universe-card:hover,.universe-card--active{border-color:var(--primary-color,#52c41a);box-shadow:0 0 0 2px rgba(82,196,26,.1)}.universe-card__head,.universe-card__stats{display:flex;align-items:center;justify-content:space-between;gap:8px}.universe-card__name{color:#172033;font-size:14px;font-weight:700}.universe-card__code,.universe-detail__eyebrow{color:#8a94a6;font-family:Consolas,Monaco,monospace;font-size:11px}.universe-card__stats{margin-top:10px;color:#7b8494;font-size:11px}.universe-card__stats strong{color:#475467}.universe-card__selected{display:block;margin-top:9px;color:var(--primary-color,#52c41a);font-size:11px}.universe-detail{min-height:0;padding:22px;overflow-y:auto;overscroll-behavior:contain;background:#fff}.universe-detail__heading{align-items:flex-start}.universe-detail__heading h3{margin:4px 0 6px;color:#172033;font-size:21px}.universe-detail__heading p{margin:0;color:#667085}.universe-detail__actions{display:flex;gap:8px}.universe-detail__facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:20px 0}.universe-detail__facts>div{padding:11px 12px;border:1px solid #e7eaf0;border-radius:8px;background:#fafbfc}.universe-detail__facts span,.universe-detail__facts strong{display:block}.universe-detail__facts span{margin-bottom:4px;color:#8a94a6;font-size:11px}.universe-detail__facts strong{color:#273044;font-size:12px}.universe-detail__section{margin-top:18px}.universe-detail__section h4{margin:0 0 9px;color:#273044;font-size:13px}.universe-detail__section pre{margin:0;padding:13px;border-radius:8px;color:#d8dee9;background:#141414;font-family:Consolas,Monaco,monospace}.universe-detail__members{min-height:230px}.universe-member-table-wrap{max-height:280px;overflow:auto;border:1px solid #e7eaf0;border-radius:8px}.universe-member-table{width:100%;border-collapse:collapse}.universe-member-table th,.universe-member-table td{padding:9px 11px;border-bottom:1px solid #edf0f3;text-align:left}.universe-member-table th{position:sticky;top:0;color:#667085;background:#f7f8fa;font-size:11px}.universe-member-table td{font-size:12px}.universe-detail-empty{margin-top:180px}.universe-create-label{display:block;margin:14px 0 6px;font-weight:700}.universe-create-full{width:100%}.universe-create-modal small{display:block;margin-top:6px;color:#8a94a6}
.universe-library-modal--dark{.ant-modal-content,.ant-modal-header,.ant-modal-body{border-color:rgba(255,255,255,.08);background:#141414}.ant-modal-title,.ant-modal-close,.universe-library-intro strong,.universe-card__name,.universe-detail__heading h3,.universe-detail__section h4,.universe-detail__facts strong{color:rgba(255,255,255,.9)}.universe-library-intro,.universe-library-workspace,.universe-library-list,.universe-card,.universe-detail,.universe-detail__facts>div,.universe-member-table-wrap{border-color:rgba(255,255,255,.09)}.universe-library-intro,.universe-library-list,.universe-detail__facts>div{background:#181818}.universe-card,.universe-detail{background:#1d1d1d}.universe-card__stats strong,.universe-library-intro span,.universe-detail__heading p,.universe-detail__facts span{color:rgba(255,255,255,.52)}.ant-input,.ant-select-selection,.ant-btn:not(.ant-btn-primary){border-color:rgba(255,255,255,.12);color:rgba(255,255,255,.82);background:#202020}.ant-alert-info{border-color:rgba(24,144,255,.28);background:rgba(24,144,255,.1)}.ant-alert-message,.ant-empty-description{color:rgba(255,255,255,.72)}.universe-member-table th{color:rgba(255,255,255,.58);background:#242424}.universe-member-table th,.universe-member-table td{border-color:rgba(255,255,255,.08)}}
.universe-library-dropdown--dark{color:rgba(255,255,255,.82);background:#202020}.universe-library-dropdown--dark .ant-select-dropdown-menu-item{color:rgba(255,255,255,.78)}.universe-library-dropdown--dark .ant-select-dropdown-menu-item:hover,.universe-library-dropdown--dark .ant-select-dropdown-menu-item-active,.universe-library-dropdown--dark .ant-select-dropdown-menu-item-selected{color:#fff;background:#303030}.universe-create-modal--dark .ant-modal-content,.universe-create-modal--dark .ant-modal-header,.universe-create-modal--dark .ant-modal-body,.universe-create-modal--dark .ant-modal-footer{border-color:rgba(255,255,255,.1);color:rgba(255,255,255,.82);background:#181818}.universe-create-modal--dark .ant-modal-title,.universe-create-modal--dark .universe-create-label{color:rgba(255,255,255,.9)}.universe-create-modal--dark .ant-input,.universe-create-modal--dark .ant-select-selection{border-color:rgba(255,255,255,.12);color:rgba(255,255,255,.82);background:#202020}
.universe-detail__section-head>div{min-width:0}.universe-detail__section-head h4{margin-bottom:4px}.universe-detail__section-head p{margin:0;color:#8a94a6;font-size:11px}.universe-detail__section-head+pre{margin-top:10px}.universe-library-modal--dark .universe-detail__section-head p{color:rgba(255,255,255,.52)}
.universe-library-modal {
  .ant-modal {
    top: 16px;
    max-width: calc(100vw - 32px);
    padding-bottom: 16px;
  }

  .ant-btn,
  .ant-radio-button-wrapper {
    font-weight: 600;
  }

  .ant-radio-button-wrapper {
    height: 36px;
    line-height: 34px;
  }

  .ant-radio-button-wrapper-checked:not(.ant-radio-button-wrapper-disabled) {
    z-index: 1;
    border-color: #faad14;
    color: #171717;
    background: #faad14;
    box-shadow: -1px 0 0 0 #faad14;
  }

  .ant-radio-button-wrapper-checked:not(.ant-radio-button-wrapper-disabled):hover {
    border-color: #ffc53d;
    color: #171717;
    background: #ffc53d;
  }

  .universe-apply-button.ant-btn-primary {
    min-height: 36px;
    border-color: #faad14;
    color: #171717;
    background: #faad14;
    box-shadow: 0 4px 12px rgba(250, 173, 20, .18);
  }

  .universe-apply-button.ant-btn-primary:hover,
  .universe-apply-button.ant-btn-primary:focus {
    border-color: #ffc53d;
    color: #171717;
    background: #ffc53d;
  }

  .universe-apply-button.ant-btn-primary[disabled] {
    border-color: #d9d9d9;
    color: rgba(0, 0, 0, .4);
    background: #f5f5f5;
    box-shadow: none;
  }
}

.universe-create-button.ant-btn {
  display: inline-flex;
  min-height: 36px;
  padding: 0 16px;
  align-items: center;
  justify-content: center;
  border-color: #d48806;
  color: #874d00;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  background: #fff7e6;
  box-shadow: 0 2px 8px rgba(250, 173, 20, .12);
}

.universe-create-button.ant-btn:hover,
.universe-create-button.ant-btn:focus {
  border-color: #faad14;
  color: #613400;
  background: #fff1b8;
}

.universe-library-tools {
  flex-wrap: wrap;
}

.universe-library-tools .ant-input-affix-wrapper {
  width: clamp(220px, 28vw, 300px);
}

.universe-library-workspace {
  height: clamp(280px, calc(100vh - 390px), 620px);
  min-height: 280px;
}

.universe-card {
  transition: border-color .16s ease, background-color .16s ease, box-shadow .16s ease, transform .16s ease;
}

.universe-card:hover {
  transform: translateY(-1px);
}

.universe-card--active {
  border-color: #faad14;
  background: #fffdf3;
  box-shadow: inset 3px 0 0 #faad14, 0 0 0 1px rgba(250, 173, 20, .16);
}

.universe-member-table-wrap {
  max-height: none;
  overflow: visible;
}

.universe-library-modal--dark {
  .universe-create-button.ant-btn {
    border-color: rgba(250, 173, 20, .72);
    color: #ffd666;
    background: rgba(250, 173, 20, .11);
    box-shadow: 0 2px 10px rgba(0, 0, 0, .2);
  }

  .universe-create-button.ant-btn:hover,
  .universe-create-button.ant-btn:focus {
    border-color: #faad14;
    color: #ffe58f;
    background: rgba(250, 173, 20, .19);
  }

  .universe-card--active {
    border-color: #faad14;
    background: rgba(250, 173, 20, .075);
    box-shadow: inset 3px 0 0 #faad14, 0 0 0 1px rgba(250, 173, 20, .14);
  }

  .universe-card__selected {
    color: #ffd666;
  }

  .universe-apply-button.ant-btn-primary[disabled] {
    border-color: rgba(255, 255, 255, .12);
    color: rgba(255, 255, 255, .34);
    background: rgba(255, 255, 255, .06);
  }
}

.universe-create-modal {
  .ant-btn-primary {
    border-color: #faad14;
    color: #171717;
    font-weight: 700;
    background: #faad14;
  }

  .ant-btn-primary:hover,
  .ant-btn-primary:focus {
    border-color: #ffc53d;
    color: #171717;
    background: #ffc53d;
  }

  .ant-btn-primary[disabled] {
    border-color: #d9d9d9 !important;
    color: rgba(0, 0, 0, .32) !important;
    background: #f5f5f5 !important;
  }
}

.universe-create-modal--dark .ant-btn-primary[disabled] {
  border-color: rgba(255, 255, 255, .12) !important;
  color: rgba(255, 255, 255, .34) !important;
  background: rgba(255, 255, 255, .06) !important;
}

@media(max-width:900px){.universe-library-tools .ant-input-affix-wrapper{width:100%}.universe-library-tools .ant-radio-group{overflow-x:auto;white-space:nowrap}.universe-library-workspace{grid-template-columns:1fr;height:clamp(260px,calc(100vh - 430px),560px);min-height:260px}.universe-library-list{max-height:240px;border-right:0;border-bottom:1px solid #e6e9ef}.universe-detail{padding:16px}.universe-detail__heading{flex-direction:column}.universe-detail__facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
