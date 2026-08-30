<template>
  <div class="library-page" :class="{ 'theme-dark': isDarkTheme }">
    <header class="library-header">
      <div>
        <span class="eyebrow">DataVest Research Library</span>
        <h1>{{ $t('community.title') }}</h1>
        <p>{{ $t('community.marketRiskTip') }}</p>
      </div>
      <a-tag color="green"><a-icon type="unlock" /> Free · source visible</a-tag>
    </header>

    <a-tabs v-model="activeTab" @change="handleTabChange">
      <a-tab-pane key="market" :tab="$t('community.title')">
        <div class="toolbar">
          <a-input-search
            v-model="keyword"
            :placeholder="$t('community.searchPlaceholder')"
            allow-clear
            @search="reloadMarket"
          />
          <a-radio-group v-model="assetType" button-style="solid" @change="reloadMarket">
            <a-radio-button value="indicator">{{ $t('community.tabIndicators') }}</a-radio-button>
            <a-radio-button value="script_template">{{ $t('community.tabScriptTemplates') }}</a-radio-button>
          </a-radio-group>
          <a-select v-model="sortBy" @change="reloadMarket">
            <a-select-option value="score">{{ $t('community.sortScore') }}</a-select-option>
            <a-select-option value="newest">{{ $t('community.sortNewest') }}</a-select-option>
            <a-select-option value="hot">{{ $t('community.sortHot') }}</a-select-option>
            <a-select-option value="rating">{{ $t('community.sortRating') }}</a-select-option>
          </a-select>
        </div>

        <a-spin :spinning="loading">
          <a-empty v-if="!loading && !items.length" />
          <div v-else class="asset-grid">
            <button v-for="item in items" :key="item.id" class="asset-card" type="button" @click="openDetail(item.id)">
              <div class="card-topline">
                <a-tag :color="item.asset_type === 'script_template' ? 'purple' : 'blue'">
                  {{ item.asset_type === 'script_template' ? $t('community.tabScriptTemplates') : $t('community.tabIndicators') }}
                </a-tag>
                <span><a-icon type="eye" /> {{ item.view_count || 0 }}</span>
              </div>
              <h3>{{ item.name }}</h3>
              <p>{{ item.description || '—' }}</p>
              <div class="card-footer">
                <span>{{ authorName(item) }}</span>
                <strong><a-icon type="fork" /> Fork</strong>
              </div>
            </button>
          </div>
        </a-spin>

        <a-pagination
          v-if="pagination.total > pagination.pageSize"
          class="pagination"
          :current="pagination.current"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @change="changePage"
        />
      </a-tab-pane>

      <a-tab-pane key="mine" :tab="$t('community.authorTab')">
        <a-spin :spinning="authorLoading">
          <a-empty v-if="!authorLoading && !authorItems.length" />
          <a-list v-else :data-source="authorItems" bordered>
            <a-list-item slot="renderItem" slot-scope="item">
              <a-list-item-meta :title="item.name" :description="item.review_note || item.description || '—'" />
              <a-tag :color="statusColor(item.review_status)">{{ item.review_status || 'approved' }}</a-tag>
              <a-popconfirm title="Unpublish this item?" @confirm="unpublish(item.id)">
                <a-button type="link" icon="disconnect">Unpublish</a-button>
              </a-popconfirm>
            </a-list-item>
          </a-list>
        </a-spin>
      </a-tab-pane>

      <a-tab-pane v-if="isAdmin" key="review" :tab="$t('community.admin.reviewTab')">
        <a-spin :spinning="reviewLoading">
          <a-empty v-if="!reviewLoading && !reviewItems.length" />
          <a-list v-else :data-source="reviewItems" bordered>
            <a-list-item slot="renderItem" slot-scope="item">
              <a-list-item-meta :title="item.name" :description="`${authorName(item)} · ${item.description || '—'}`" />
              <a-button type="link" icon="eye" @click="openDetail(item.id)">Review source</a-button>
              <a-button type="link" icon="check" @click="review(item.id, 'approve')">Approve</a-button>
              <a-button type="link" icon="close" class="danger" @click="review(item.id, 'reject')">Reject</a-button>
            </a-list-item>
          </a-list>
        </a-spin>
      </a-tab-pane>
    </a-tabs>

    <a-drawer
      :visible="detailVisible"
      :title="detail && detail.name"
      width="min(760px, 92vw)"
      @close="detailVisible = false"
    >
      <a-spin :spinning="detailLoading">
        <template v-if="detail">
          <div class="detail-meta">
            <a-tag color="green">Free</a-tag>
            <a-tag color="cyan"><a-icon type="eye" /> Source visible</a-tag>
            <span>{{ authorName(detail) }}</span>
          </div>
          <p>{{ detail.description || '—' }}</p>
          <pre class="source-code"><code>{{ detail.code }}</code></pre>
          <a-button type="primary" icon="fork" :loading="forking" @click="forkDetail">Fork to my workspace</a-button>
        </template>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script>
import request from '@/utils/request'

export default {
  name: 'FreeResearchLibrary',
  data () {
    return {
      activeTab: 'market',
      assetType: 'indicator',
      sortBy: 'score',
      keyword: '',
      loading: false,
      items: [],
      pagination: { current: 1, pageSize: 12, total: 0 },
      detailVisible: false,
      detailLoading: false,
      detail: null,
      forking: false,
      authorLoading: false,
      authorItems: [],
      reviewLoading: false,
      reviewItems: []
    }
  },
  computed: {
    isDarkTheme () {
      return this.$store?.state?.app?.theme === 'dark'
    },
    isAdmin () {
      const role = this.$store?.getters?.roles || this.$store?.getters?.userRole || ''
      const values = Array.isArray(role) ? role : [role && (role.id || role)]
      return values.map(value => String(value || '').toLowerCase()).includes('admin')
    }
  },
  mounted () {
    this.loadMarket()
  },
  methods: {
    authorName (item) {
      return item.author_nickname || item.author_username || `#${item.author_id || '—'}`
    },
    statusColor (status) {
      return { pending: 'orange', approved: 'green', rejected: 'red' }[status] || 'green'
    },
    async loadMarket () {
      this.loading = true
      try {
        const res = await request({
          url: '/api/community/indicators',
          method: 'get',
          params: {
            page: this.pagination.current,
            page_size: this.pagination.pageSize,
            keyword: this.keyword || undefined,
            sort_by: this.sortBy,
            asset_type: this.assetType
          }
        })
        if (res.code !== 1) throw new Error('library_unavailable')
        this.items = res.data.items || []
        this.pagination.total = Number(res.data.total || 0)
      } catch (error) {
        this.items = []
        this.$message.error(this.$t('community.loadFailed'))
      } finally {
        this.loading = false
      }
    },
    reloadMarket () {
      this.pagination.current = 1
      this.loadMarket()
    },
    changePage (page) {
      this.pagination.current = page
      this.loadMarket()
    },
    async openDetail (id) {
      this.detailVisible = true
      this.detailLoading = true
      this.detail = null
      try {
        const res = await request({ url: `/api/community/indicators/${id}`, method: 'get' })
        if (res.code !== 1 || !res.data || !res.data.source_visible || !res.data.code) throw new Error('source_unavailable')
        this.detail = res.data
      } catch (error) {
        this.$message.error(this.$t('community.loadFailed'))
        this.detailVisible = false
      } finally {
        this.detailLoading = false
      }
    },
    async forkDetail () {
      if (!this.detail) return
      this.forking = true
      try {
        const res = await request({ url: `/api/community/indicators/${this.detail.id}/fork`, method: 'post' })
        if (res.code !== 1) throw new Error('fork_failed')
        this.$message.success(res.msg || 'Fork created')
        const localId = res.data && res.data.local_copy_id
        const path = this.detail.asset_type === 'script_template' ? '/strategy-ide' : '/indicator-ide'
        const query = this.detail.asset_type === 'script_template'
          ? { sourceId: String(this.detail.source_script_source_id || '') }
          : { indicator_id: String(localId || '') }
        this.$router.push({ path, query })
      } catch (error) {
        this.$message.error((error.response && error.response.data && error.response.data.msg) || 'Fork failed')
      } finally {
        this.forking = false
      }
    },
    handleTabChange (tab) {
      if (tab === 'mine') this.loadMine()
      if (tab === 'review' && this.isAdmin) this.loadReview()
    },
    async loadMine () {
      this.authorLoading = true
      try {
        const res = await request({ url: '/api/community/author/published', method: 'get', params: { page: 1, page_size: 50 } })
        this.authorItems = res.code === 1 ? (res.data.items || []) : []
      } finally {
        this.authorLoading = false
      }
    },
    async unpublish (id) {
      const res = await request({ url: `/api/community/author/indicators/${id}/unpublish`, method: 'post', data: {} })
      if (res.code === 1) {
        this.$message.success(res.msg || 'Unpublished')
        await this.loadMine()
        await this.loadMarket()
      }
    },
    async loadReview () {
      this.reviewLoading = true
      try {
        const res = await request({ url: '/api/community/admin/pending-indicators', method: 'get', params: { page: 1, page_size: 50, review_status: 'pending' } })
        this.reviewItems = res.code === 1 ? (res.data.items || []) : []
      } finally {
        this.reviewLoading = false
      }
    },
    async review (id, action) {
      const res = await request({ url: `/api/community/admin/indicators/${id}/review`, method: 'post', data: { action, note: '' } })
      if (res.code === 1) {
        this.$message.success(res.msg)
        await this.loadReview()
        await this.loadMarket()
      }
    }
  }
}
</script>

<style lang="less" scoped>
.library-page { min-height: calc(100vh - 64px); padding: 24px; background: #f4f6f8; color: #1f2937; }
.library-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 8px; }
.library-header h1 { margin: 4px 0; font-size: 30px; }
.library-header p { max-width: 720px; margin: 0; color: #667085; }
.eyebrow { color: #389e0d; font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.toolbar { display: grid; grid-template-columns: minmax(220px, 1fr) auto 180px; gap: 12px; margin-bottom: 18px; }
.asset-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.asset-card { min-height: 190px; padding: 17px; border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; color: inherit; text-align: left; cursor: pointer; transition: transform .18s, border-color .18s; }
.asset-card:hover { border-color: #52c41a; transform: translateY(-2px); }
.asset-card h3 { margin: 18px 0 8px; font-size: 18px; }
.asset-card p { display: -webkit-box; min-height: 42px; overflow: hidden; color: #667085; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.card-topline, .card-footer, .detail-meta { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.card-footer { margin-top: 18px; color: #667085; }
.card-footer strong { color: #389e0d; }
.pagination { margin-top: 18px; text-align: right; }
.source-code { max-height: 58vh; overflow: auto; padding: 18px; border-radius: 10px; background: #111827; color: #d1fae5; white-space: pre-wrap; }
.danger { color: #cf1322; }
.theme-dark { background: #0b0b0b; color: #f5f5f5; }
.theme-dark .library-header p, .theme-dark .asset-card p, .theme-dark .card-footer { color: #a7a7a7; }
.theme-dark .asset-card { border-color: #303030; background: #151515; }
@media (max-width: 960px) { .asset-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .library-page { padding: 14px; } .toolbar, .asset-grid { grid-template-columns: 1fr; } .library-header { flex-direction: column; } }
</style>
