<template>
  <p v-if="data.status && data.freshness !== 'FRESH' && data.status !== 'UNAVAILABLE'" class="data-freshness-notice" role="status">
    <a-icon type="clock-circle" /> {{ $t('smartInsights.widgetFreshnessWarning') }}
    <span v-if="data.effectiveAt"> · {{ $t('smartInsights.dataPeriod') }}: {{ formatDate(data.effectiveAt) }}</span>
  </p>
</template>
<script>
import { formatVietnamDate } from '@/utils/vietnamTime'
export default {
  name: 'DataFreshnessNotice',
  props: { data: { type: Object, default: () => ({}) } },
  methods: { formatDate (value) { return formatVietnamDate(value, { locale: this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US', fallback: '—' }) } }
}
</script>
<style scoped>
.data-freshness-notice { margin: 10px 0; padding: 9px 12px; border-radius: 6px; background: #fff7e6; color: #805b12; font-size: 12px; line-height: 1.5; }
</style>
