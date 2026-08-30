<template>
  <div class="universe-page" :class="{ 'theme-dark': isDarkTheme }">
    <header class="page-header">
      <div>
        <span class="kicker">{{ t('universeManager.kicker') }}</span>
        <h1>{{ t('universeManager.title') }}</h1>
        <p>{{ t('universeManager.subtitle') }}</p>
      </div>
      <div class="header-actions">
        <a-button icon="reload" :loading="loading" @click="loadUniverses">{{ t('universeManager.reload') }}</a-button>
        <a-button type="primary" icon="plus" @click="openCreate">{{ t('universeManager.create') }}</a-button>
      </div>
    </header>

    <section class="summary-row">
      <div class="summary-card"><span>{{ t('universeManager.summary.system') }}</span><strong>{{ systemUniverses.length }}</strong></div>
      <div class="summary-card"><span>{{ t('universeManager.summary.personal') }}</span><strong>{{ personalUniverses.length }}</strong></div>
      <div class="summary-card"><span>{{ t('universeManager.summary.coverage') }}</span><strong>{{ totalSystemMembers.toLocaleString() }}</strong></div>
      <div class="summary-card"><span>{{ t('universeManager.summary.updated') }}</span><strong class="summary-date">{{ latestSystemDate }}</strong></div>
    </section>

    <section class="workspace-card">
      <a-tabs v-model="activeTab">
        <a-tab-pane key="system">
          <span slot="tab"><a-icon type="database" />{{ t('universeManager.tabs.system') }}</span>
        </a-tab-pane>
        <a-tab-pane key="personal">
          <span slot="tab"><a-icon type="folder" />{{ t('universeManager.tabs.personal') }}</span>
        </a-tab-pane>
        <a-tab-pane key="watchlist">
          <span slot="tab"><a-icon type="star" />{{ t('universeManager.tabs.watchlist') }}</span>
        </a-tab-pane>
      </a-tabs>

      <div class="toolbar">
        <a-input-search v-model="keyword" allowClear :placeholder="t('universeManager.search')" />
        <a-select v-model="marketFilter">
          <a-select-option value="all">{{ t('universeManager.allMarkets') }}</a-select-option>
          <a-select-option v-for="market in markets" :key="market" :value="market">{{ marketText(market) }}</a-select-option>
        </a-select>
      </div>

      <a-spin :spinning="loading">
        <div v-if="visibleUniverses.length" class="catalog-grid">
          <article v-for="item in visibleUniverses" :key="item.id" class="universe-item">
            <div class="item-topline">
              <div class="universe-icon" :class="marketClass(item.market)"><a-icon :type="marketIcon(item.market)" /></div>
              <div class="item-title">
                <strong>{{ universeLabel(item) }}</strong>
                <span>{{ marketText(item.market) }}</span>
              </div>
              <a-tag :color="item.status === 'active' ? 'green' : 'orange'">{{ statusText(item.status) }}</a-tag>
            </div>
            <div class="item-stats">
              <div><span>{{ t('universeManager.members') }}</span><strong>{{ Number(item.member_count || 0).toLocaleString() }}</strong></div>
              <div><span>{{ t('universeManager.version') }}</span><strong>{{ universeVersion(item) }}</strong></div>
            </div>
            <div class="item-actions">
              <a-button size="small" icon="unordered-list" @click="viewMembers(item)">{{ t('universeManager.viewMembers') }}</a-button>
              <a-button v-if="item.is_system && item.code !== 'watchlist'" size="small" icon="copy" :loading="cloningId === item.id" @click="clone(item)">{{ t('universeManager.copyToMine') }}</a-button>
              <a-button v-if="isEditable(item)" size="small" icon="edit" @click="editUniverse(item)">{{ t('universeManager.edit') }}</a-button>
            </div>
          </article>
        </div>
        <a-empty v-else :description="t('universeManager.empty')" />
      </a-spin>
    </section>

    <a-modal
      v-model="editorVisible"
      :title="editingId ? t('universeManager.edit') : t('universeManager.create')"
      :confirmLoading="saving"
      :okText="t('universeManager.save')"
      :cancelText="t('universeManager.cancel')"
      @ok="save"
      @cancel="resetForm">
      <label class="field-label">{{ t('universeManager.name') }}</label>
      <a-input v-model="form.name" :disabled="!!editingId" />
      <label class="field-label">{{ t('universeManager.market') }}</label>
      <a-select v-model="form.market" :disabled="!!editingId" class="full-width">
        <a-select-option v-for="market in markets" :key="market" :value="market">{{ marketText(market) }}</a-select-option>
      </a-select>
      <label class="field-label">{{ t('universeManager.members') }}</label>
      <a-textarea v-model="form.memberText" :rows="10" :placeholder="memberPlaceholder" />
      <small class="field-hint">{{ t('universeManager.memberHint') }}</small>
    </a-modal>

    <a-drawer :visible="drawerVisible" :title="drawerTitle" width="min(760px, 92vw)" @close="drawerVisible = false">
      <div class="drawer-toolbar">
        <a-input-search v-model="memberKeyword" allowClear :placeholder="t('universeManager.searchMembers')" />
        <a-tag>{{ filteredMembers.length }} {{ t('universeManager.symbols') }}</a-tag>
      </div>
      <a-spin :spinning="membersLoading">
        <div class="member-table-wrap">
          <table class="member-table">
            <thead><tr><th>{{ t('universeManager.symbol') }}</th><th>{{ t('universeManager.memberName') }}</th><th>{{ t('universeManager.market') }}</th><th>{{ t('universeManager.weight') }}</th></tr></thead>
            <tbody>
              <tr v-for="member in pagedMembers" :key="`${member.market}-${member.symbol}`">
                <td><strong>{{ member.symbol }}</strong></td><td>{{ member.name || '-' }}</td><td>{{ marketText(member.market) }}</td><td>{{ formatWeight(member.weight) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <a-pagination
          v-if="filteredMembers.length > memberPageSize"
          v-model="memberPage"
          :pageSize="memberPageSize"
          :total="filteredMembers.length"
          show-less-items
          class="member-pagination" />
      </a-spin>
    </a-drawer>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import { cloneUniverse, createUniverse, getUniverseMembers, getUniverses, replaceUniverseMembers } from '@/api/universe'
import { ACTIVE_MARKET_ORDER } from '@/utils/supportedMarkets'

export default {
  name: 'UniverseManager',
  data () {
    return {
      loading: false,
saving: false,
membersLoading: false,
cloningId: 0,
      activeTab: 'system',
keyword: '',
marketFilter: 'all',
universes: [],
      markets: [...ACTIVE_MARKET_ORDER, 'Mixed'],
      editorVisible: false,
editingId: 0,
form: { name: '', market: 'VNStock', memberText: '' },
      drawerVisible: false,
drawerUniverse: null,
members: [],
memberKeyword: '',
memberPage: 1,
memberPageSize: 50
    }
  },
  computed: {
    ...mapState({ navTheme: state => state.app.theme }),
    isDarkTheme () { return ['dark', 'realdark'].includes(this.navTheme) },
    systemUniverses () { return this.universes.filter(item => item.is_system && item.code !== 'watchlist') },
    personalUniverses () { return this.universes.filter(item => !item.is_system) },
    watchlistUniverses () { return this.universes.filter(item => item.code === 'watchlist') },
    tabUniverses () {
      if (this.activeTab === 'personal') return this.personalUniverses
      if (this.activeTab === 'watchlist') return this.watchlistUniverses
      return this.systemUniverses
    },
    visibleUniverses () {
      const keyword = this.keyword.trim().toLowerCase()
      return this.tabUniverses.filter(item => {
        if (this.marketFilter !== 'all' && item.market !== this.marketFilter) return false
        return !keyword || `${this.universeLabel(item)} ${item.code} ${item.market}`.toLowerCase().includes(keyword)
      })
    },
    totalSystemMembers () { return this.systemUniverses.reduce((sum, item) => sum + Number(item.member_count || 0), 0) },
    latestSystemDate () {
      const values = this.systemUniverses.map(item => this.universeVersion(item)).filter(value => value && value !== '-')
      return values.sort().reverse()[0] || '-'
    },
    memberPlaceholder () { return this.form.market === 'Mixed' ? this.t('universeManager.mixedPlaceholder') : this.t('universeManager.placeholder') },
    drawerTitle () { return this.drawerUniverse ? this.universeLabel(this.drawerUniverse) : this.t('universeManager.members') },
    filteredMembers () {
      const keyword = this.memberKeyword.trim().toLowerCase()
      if (!keyword) return this.members
      return this.members.filter(item => `${item.symbol} ${item.name || ''} ${item.market}`.toLowerCase().includes(keyword))
    },
    pagedMembers () {
      const start = (this.memberPage - 1) * this.memberPageSize
      return this.filteredMembers.slice(start, start + this.memberPageSize)
    }
  },
  watch: {
    memberKeyword () { this.memberPage = 1 }
  },
  mounted () { this.loadUniverses() },
  methods: {
    t (key) { return this.$t(key) },
    unwrap (res) { return res && Object.prototype.hasOwnProperty.call(res, 'data') ? res.data : res },
    universeLabel (item) { const translated = item.name_i18n_key ? this.t(item.name_i18n_key) : ''; return translated && translated !== item.name_i18n_key ? translated : (item.name || item.code) },
    universeVersion (item) { return (item.metadata && item.metadata.snapshot_as_of) || (item.updated_at ? String(item.updated_at).slice(0, 10) : '-') },
    statusText (status) { return this.t(`universeManager.status.${status || 'data_required'}`) },
    marketText (market) { return this.t(`universeManager.market.${market || 'Mixed'}`) },
    marketIcon (market) { return { Crypto: 'thunderbolt', VNStock: 'stock', Forex: 'gold', USStock: 'global' }[market] || 'appstore' },
    marketClass (market) { return `market-${String(market || 'mixed').toLowerCase()}` },
    isEditable (item) { return !item.is_system && item.universe_type === 'manual' },
    formatWeight (value) { return value === null || value === undefined ? '-' : `${(Number(value) * 100).toFixed(2)}%` },
    async loadUniverses () {
      this.loading = true
      try { this.universes = this.unwrap(await getUniverses()) || [] } catch (error) { this.$message.error(error.backendMessage || error.message || this.t('universeManager.loadFailed')) } finally { this.loading = false }
    },
    openCreate () { this.resetForm(); this.editorVisible = true },
    parseMembers () {
      const entries = this.form.memberText.split(/[\n,;]+/).map(item => item.trim()).filter(Boolean)
      return entries.map(entry => {
        if (this.form.market !== 'Mixed') return { market: this.form.market, symbol: entry }
        const separator = entry.indexOf(':')
        if (separator <= 0) throw new Error(this.t('universeManager.mixedFormatError'))
        return { market: entry.slice(0, separator).trim(), symbol: entry.slice(separator + 1).trim() }
      })
    },
    async save () {
      if (!this.form.name.trim() || !this.form.memberText.trim()) return
      this.saving = true
      try {
        const members = this.parseMembers()
        if (this.editingId) await replaceUniverseMembers(this.editingId, members)
        else await createUniverse({ name: this.form.name.trim(), market: this.form.market, universeType: 'manual', members })
        this.$message.success(this.t('universeManager.saved'))
        this.editorVisible = false
        this.resetForm()
        this.activeTab = 'personal'
        await this.loadUniverses()
      } catch (error) { this.$message.error(error.backendMessage || error.message || this.t('universeManager.saveFailed')) } finally { this.saving = false }
    },
    async editUniverse (item) {
      try {
        const payload = this.unwrap(await getUniverseMembers(item.id)) || {}
        this.editingId = item.id
        this.form.name = item.name || item.code
        this.form.market = item.market
        this.form.memberText = (payload.members || []).map(member => item.market === 'Mixed' ? `${member.market}:${member.symbol}` : member.symbol).join('\n')
        this.editorVisible = true
      } catch (error) { this.$message.error(error.backendMessage || error.message || this.t('universeManager.loadMembersFailed')) }
    },
    async viewMembers (item) {
      this.drawerUniverse = item; this.members = []; this.memberKeyword = ''; this.memberPage = 1; this.drawerVisible = true; this.membersLoading = true
      try { const payload = this.unwrap(await getUniverseMembers(item.id)) || {}; this.members = payload.members || [] } catch (error) { this.$message.error(error.backendMessage || error.message || this.t('universeManager.loadMembersFailed')) } finally { this.membersLoading = false }
    },
    async clone (item) {
      this.cloningId = item.id
      try {
        await cloneUniverse(item.id, { name: `${this.universeLabel(item)} ${this.t('universeManager.copySuffix')}` })
        this.$message.success(this.t('universeManager.copied'))
        this.activeTab = 'personal'
        await this.loadUniverses()
      } catch (error) { this.$message.error(error.backendMessage || error.message || this.t('universeManager.copyFailed')) } finally { this.cloningId = 0 }
    },
    resetForm () { this.editingId = 0; this.form = { name: '', market: 'VNStock', memberText: '' } }
  }
}
</script>

<style lang="less" scoped>
.member-pagination{margin-top:14px;text-align:right}
.universe-page{min-height:calc(100vh - 64px);padding:20px;background:#f4f6f8;color:#1f2933}.page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:16px}.kicker{color:#52c41a;font-size:12px;font-weight:800;text-transform:uppercase}.page-header h1{margin:3px 0 4px;font-size:28px}.page-header p{margin:0;color:#667085}.header-actions{display:flex;gap:8px}.summary-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}.summary-card{display:flex;flex-direction:column;gap:5px;padding:15px 17px;border:1px solid #e5e7eb;border-radius:10px;background:#fff}.summary-card span{color:#667085;font-size:12px}.summary-card strong{font-size:23px}.summary-card .summary-date{font-size:18px}.workspace-card{min-height:480px;padding:0 18px 18px;border:1px solid #e5e7eb;border-radius:10px;background:#fff}.toolbar{display:flex;gap:10px;margin-bottom:14px}.toolbar .ant-input-search{max-width:360px}.toolbar .ant-select{width:180px}.catalog-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.universe-item{display:flex;min-height:190px;flex-direction:column;padding:15px;border:1px solid #e5e7eb;border-radius:10px;transition:border-color .2s,transform .2s}.universe-item:hover{border-color:#52c41a;transform:translateY(-1px)}.item-topline{display:flex;align-items:center;gap:10px}.universe-icon{display:flex;width:38px;height:38px;align-items:center;justify-content:center;border-radius:9px;background:#edf7e8;color:#52c41a;font-size:17px}.market-crypto{background:#fff5e6;color:#fa8c16}.market-hkstock{background:#fff0f6;color:#eb2f96}.market-usstock{background:#eaf3ff;color:#1677ff}.item-title{display:flex;min-width:0;flex:1;flex-direction:column}.item-title strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.item-title span{color:#667085;font-size:12px}.item-stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:17px 0}.item-stats>div{display:flex;flex-direction:column;padding:9px;border-radius:7px;background:#f7f8fa}.item-stats span{color:#667085;font-size:11px}.item-stats strong{margin-top:2px;font-size:15px}.item-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto}.field-label{display:block;margin:14px 0 6px;font-weight:700}.full-width{width:100%}.field-hint{display:block;margin-top:6px;color:#98a2b3}.drawer-toolbar{display:flex;align-items:center;gap:12px;margin-bottom:12px}.drawer-toolbar .ant-input-search{max-width:360px}.member-table-wrap{overflow:auto;border:1px solid #e5e7eb;border-radius:8px}.member-table{width:100%;border-collapse:collapse}.member-table th,.member-table td{padding:10px 12px;border-bottom:1px solid #edf0f3;text-align:left}.member-table th{background:#f7f8fa;color:#667085;font-size:12px}.theme-dark{background:#0b0b0b;color:#f5f5f5}.theme-dark h1{color:#f5f5f5}.theme-dark .summary-card,.theme-dark .workspace-card{border-color:#2b2b2b;background:#151515}.theme-dark .summary-card span,.theme-dark .page-header p,.theme-dark .item-title span,.theme-dark .item-stats span{color:#a7a7a7}.theme-dark .universe-item{border-color:#2b2b2b}.theme-dark .item-stats>div{background:#1d1d1d}.theme-dark .member-table-wrap{border-color:#303030}.theme-dark .member-table th{background:#1d1d1d}.theme-dark .member-table th,.theme-dark .member-table td{border-color:#303030}@media(max-width:1200px){.catalog-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){.universe-page{padding:14px}.page-header{flex-direction:column}.summary-row{grid-template-columns:repeat(2,minmax(0,1fr))}.catalog-grid{grid-template-columns:1fr}.toolbar{flex-direction:column}.toolbar .ant-input-search,.toolbar .ant-select{width:100%;max-width:none}}
</style>
