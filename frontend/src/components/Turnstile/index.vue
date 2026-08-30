<template>
  <div class="turnstile-container" v-if="enabled">
    <div ref="turnstileRef" :id="containerId"></div>
    <div v-if="error" class="turnstile-error">
      {{ error }}
      <a @click="reset">{{ $t('user.security.retry') || 'Retry' }}</a>
    </div>
  </div>
</template>

<script>
let turnstileScriptLoaded = false
let turnstileScriptLoading = false
const turnstileCallbacks = []

function loadTurnstileScript () {
  return new Promise((resolve, reject) => {
    if (turnstileScriptLoaded) {
      resolve()
      return
    }

    turnstileCallbacks.push({ resolve, reject })

    if (turnstileScriptLoading) {
      return
    }

    turnstileScriptLoading = true

    const script = document.createElement('script')
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
    script.async = true
    script.defer = true

    script.onload = () => {
      turnstileScriptLoaded = true
      turnstileCallbacks.forEach(cb => cb.resolve())
      turnstileCallbacks.length = 0
    }

    script.onerror = () => {
      turnstileScriptLoading = false
      turnstileCallbacks.forEach(cb => cb.reject(new Error('Failed to load Turnstile script')))
      turnstileCallbacks.length = 0
    }

    document.head.appendChild(script)
  })
}

export default {
  name: 'Turnstile',

  props: {
    siteKey: {
      type: String,
      default: ''
    },
    enabled: {
      type: Boolean,
      default: true
    },
    theme: {
      type: String,
      default: 'auto' // 'light', 'dark', 'auto'
    },
    size: {
      type: String,
      default: 'normal' // 'normal', 'compact'
    },
    appearance: {
      type: String,
      default: 'always'
    },
    execution: {
      type: String,
      default: 'render'
    },
    executeTimeoutMs: {
      type: Number,
      default: 30000
    }
  },

  data () {
    return {
      widgetId: null,
      token: null,
      error: null,
      pendingResolve: null,
      pendingReject: null,
      pendingTimer: null,
      containerId: `turnstile-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    }
  },

  mounted () {
    if (this.enabled && this.siteKey) {
      this.initTurnstile()
    }
  },

  beforeDestroy () {
    this.cleanup()
  },

  watch: {
    siteKey (newVal) {
      if (newVal && this.enabled) {
        this.initTurnstile()
      }
    },
    enabled (newVal) {
      if (newVal && this.siteKey) {
        this.initTurnstile()
      } else {
        this.cleanup()
      }
    }
  },

  methods: {
    translate (key, fallback) {
      const value = this.$t ? this.$t(key) : ''
      return value && value !== key ? value : fallback
    },

    async initTurnstile () {
      try {
        await loadTurnstileScript()
        this.renderWidget()
      } catch (e) {
        this.error = this.translate('user.security.loadFailed', 'Failed to load verification')
        console.error('Turnstile init error:', e)
      }
    },

    renderWidget () {
      if (!window.turnstile || !this.$refs.turnstileRef) {
        return
      }

      // Clean up existing widget
      this.cleanup()

      this.widgetId = window.turnstile.render(this.$refs.turnstileRef, {
        sitekey: this.siteKey,
        theme: this.theme,
        size: this.size,
        appearance: this.appearance,
        execution: this.execution,
        callback: (token) => {
          this.token = token
          this.error = null
          if (this.pendingResolve) {
            this.pendingResolve(token)
            this.clearPending()
          }
          this.$emit('success', token)
        },
        'error-callback': (code) => {
          this.token = null
          this.error = this.translate('user.security.verificationFailed', 'Verification failed')
          if (this.pendingReject) {
            this.pendingReject(code)
            this.clearPending()
          }
          if (code) {
            console.warn('Turnstile verification error:', code)
          }
          this.$emit('error', code)
        },
        'expired-callback': () => {
          this.token = null
          if (this.pendingReject) {
            this.pendingReject(new Error('expired'))
            this.clearPending()
          }
          this.$emit('expired')
        }
      })
    },

    clearPending () {
      if (this.pendingTimer) {
        clearTimeout(this.pendingTimer)
        this.pendingTimer = null
      }
      this.pendingResolve = null
      this.pendingReject = null
    },

    async execute () {
      if (!this.enabled) {
        return Promise.resolve('')
      }
      if (!window.turnstile || this.widgetId === null) {
        await this.initTurnstile()
      }
      if (!window.turnstile || this.widgetId === null) {
        return Promise.reject(new Error('turnstile_unavailable'))
      }
      if (this.pendingReject) {
        this.pendingReject(new Error('replaced'))
      }
      this.clearPending()
      this.token = null
      this.error = null
      return new Promise((resolve, reject) => {
        this.pendingResolve = resolve
        this.pendingReject = reject
        this.pendingTimer = setTimeout(() => {
          const err = new Error('turnstile_timeout')
          this.error = this.translate('user.security.verificationFailed', 'Verification failed')
          this.clearPending()
          reject(err)
          this.$emit('error', err)
        }, Math.max(5000, this.executeTimeoutMs))
        try {
          if (this.execution === 'execute') {
            window.turnstile.execute(this.widgetId)
          }
        } catch (e) {
          this.clearPending()
          reject(e)
        }
      })
    },

    reset () {
      this.token = null
      this.error = null
      if (this.pendingReject) {
        this.pendingReject(new Error('reset'))
        this.clearPending()
      }
      if (window.turnstile && this.widgetId !== null) {
        window.turnstile.reset(this.widgetId)
      } else {
        this.renderWidget()
      }
    },

    getToken () {
      return this.token
    },

    cleanup () {
      if (window.turnstile && this.widgetId !== null) {
        try {
          window.turnstile.remove(this.widgetId)
        } catch (e) {
          // Ignore cleanup errors
        }
        this.widgetId = null
      }
    }
  }
}
</script>

<style lang="less" scoped>
.turnstile-container {
  margin: 16px 0;
  display: flex;
  flex-direction: column;
  align-items: center;

  .turnstile-error {
    margin-top: 8px;
    color: #ff4d4f;
    font-size: 13px;

    a {
      margin-left: 8px;
      color: var(--primary-color, #1890ff);
      cursor: pointer;

      &:hover {
        text-decoration: underline;
      }
    }
  }
}
</style>
