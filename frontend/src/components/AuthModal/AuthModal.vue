<template>
  <a-modal
    :visible="visible"
    :title="modalTitle"
    :footer="null"
    :width="520"
    :destroy-on-close="true"
    :mask-closable="true"
    centered
    wrap-class-name="auth-modal-wrap"
    @cancel="close"
  >
    <login
      v-if="visible"
      :key="instanceKey"
      :embedded="true"
      :initial-tab="activeTab"
      :redirect="redirect"
      @authenticated="close"
      @tab-change="activeTab = $event"
    />
  </a-modal>
</template>

<script>
import Login from '@/views/user/Login.vue'
import { authModalBus, setAuthModalReady } from '@/utils/authModal'
import { resolvePostLoginPath } from '@/utils/guestAccess'

export default {
  name: 'AuthModal',
  components: { Login },
  data () {
    return {
      visible: false,
      activeTab: 'login',
      redirect: '/smart-insights',
      instanceKey: 0
    }
  },
  computed: {
    modalTitle () {
      return this.activeTab === 'register'
        ? (this.$t('user.register.tab') || 'Create account')
        : (this.$t('user.login.tab') || 'Sign in')
    }
  },
  mounted () {
    authModalBus.$on('open', this.open)
    authModalBus.$on('close', this.close)
    setAuthModalReady(true)
  },
  beforeDestroy () {
    setAuthModalReady(false)
    authModalBus.$off('open', this.open)
    authModalBus.$off('close', this.close)
  },
  methods: {
    open (options = {}) {
      const payload = typeof options === 'string' ? { redirect: options } : (options || {})
      this.activeTab = payload.tab === 'register' ? 'register' : 'login'
      this.redirect = resolvePostLoginPath(payload.redirect || (this.$route && this.$route.fullPath))
      this.instanceKey += 1
      this.visible = true
    },
    close () {
      this.visible = false
    }
  }
}
</script>

<style lang="less">
.auth-modal-wrap {
  .ant-modal {
    max-width: calc(100vw - 28px);
  }

  .ant-modal-content {
    overflow: hidden;
    border-radius: 16px;
    background: #ffffff;
    box-shadow: 0 24px 70px rgba(15, 23, 42, 0.24);
  }

  .ant-modal-header {
    padding: 20px 24px;
    border-bottom: 1px solid #edf2f7;
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  }

  .ant-modal-title {
    color: #172033;
    font-size: 18px;
    font-weight: 700;
  }

  .ant-modal-close {
    color: #64748b;
  }

  .ant-modal-body {
    padding: 0;
    background: #ffffff;
  }
}
</style>
