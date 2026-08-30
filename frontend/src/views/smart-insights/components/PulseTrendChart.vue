<template>
  <article class="pulse-trend-chart">
    <div class="chart-heading">
      <div>
        <h4>{{ title }}</h4>
        <small v-if="latest">{{ $t('smartInsights.latestValue') }}: {{ formatValue(latest.value) }} · {{ formatDate(latest.effectiveAt) }}</small>
      </div>
      <a-tag v-if="status && status !== 'AVAILABLE'" :class="statusClass">{{ statusLabel }}</a-tag>
    </div>
    <div v-if="!points.length" class="chart-empty">
      <a-icon type="line-chart" />
      <span>{{ $t('smartInsights.noHistory') }}</span>
    </div>
    <svg
      v-else
      class="trend-svg"
      viewBox="0 0 360 150"
      preserveAspectRatio="none"
      role="img"
      :aria-label="title"
    >
      <line x1="0" y1="12" x2="360" y2="12" class="grid-line" />
      <line x1="0" y1="75" x2="360" y2="75" class="grid-line" />
      <line
        x1="0"
        y1="138"
        x2="360"
        y2="138"
        class="grid-line"
      />
      <line
        v-if="zeroY !== null"
        x1="0"
        :y1="zeroY"
        x2="360"
        :y2="zeroY"
        class="zero-line"
      />
      <polyline v-if="points.length > 1" :points="linePoints" class="trend-line" />
      <circle
        v-for="point in points"
        :key="point.key"
        :cx="point.x"
        :cy="point.y"
        r="3"
        class="trend-dot"
      />
    </svg>
    <div v-if="points.length" class="chart-range"><span>{{ formatValue(min) }}</span><span>{{ formatValue(max) }}</span></div>
  </article>
</template>

<script>
export default {
  name: 'PulseTrendChart',
  props: {
    title: { type: String, default: '' },
    series: { type: Array, default: () => [] },
    status: { type: String, default: 'AVAILABLE' },
    unit: { type: String, default: '' }
  },
  computed: {
    points () {
      const values = this.series.map(item => ({
        value: Number(item && item.value),
        effectiveAt: item && item.effectiveAt
      })).filter(item => Number.isFinite(item.value) && item.effectiveAt)
      if (!values.length) return []
      const min = Math.min(...values.map(item => item.value))
      const max = Math.max(...values.map(item => item.value))
      const range = max - min || Math.max(Math.abs(max), 1)
      return values.map((item, index) => ({
        ...item,
        key: `${item.effectiveAt}-${index}`,
        x: Math.round((index / Math.max(values.length - 1, 1)) * 360),
        y: Math.round(138 - ((item.value - min) / range) * 126)
      }))
    },
    latest () { return this.points.length ? this.points[this.points.length - 1] : null },
    min () { return this.points.length ? Math.min(...this.points.map(item => item.value)) : null },
    max () { return this.points.length ? Math.max(...this.points.map(item => item.value)) : null },
    linePoints () { return this.points.map(item => `${item.x},${item.y}`).join(' ') },
    zeroY () {
      if (this.min === null || this.max === null || this.min > 0 || this.max < 0) return null
      const range = this.max - this.min || 1
      return Math.round(138 - ((0 - this.min) / range) * 126)
    },
    statusClass () { return `chart-status-${String(this.status || '').toLowerCase()}` },
    statusLabel () {
      const labels = {
        AVAILABLE: this.$t('smartInsights.availableStatus'),
        PARTIAL: this.$t('smartInsights.partialStatus'),
        STALE: this.$t('smartInsights.stale'),
        UNAVAILABLE: this.$t('smartInsights.unavailableShort')
      }
      return labels[String(this.status || 'UNAVAILABLE').toUpperCase()] || this.$t('smartInsights.unavailableShort')
    }
  },
  methods: {
    formatValue (value) {
      if (!Number.isFinite(Number(value))) return '—'
      return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(Number(value))}${this.unit ? ` ${this.unit}` : ''}`
    },
    formatDate (value) {
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? String(value || '—') : date.toLocaleDateString(this.$i18n && this.$i18n.locale === 'vi-VN' ? 'vi-VN' : 'en-US')
    }
  }
}
</script>

<style lang="less" scoped>
.pulse-trend-chart { min-width: 0; padding: 13px 14px 10px; border: 1px solid var(--line); border-radius: 9px; background: var(--card); }
.chart-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.chart-heading h4 { margin: 0; color: var(--ink); font-size: 13px; }
.chart-heading small { display: block; margin-top: 4px; color: var(--muted); font-size: 11px; }
.chart-heading .ant-tag { margin: 0; font-size: 10px; }
.chart-status-unavailable { color: var(--muted); }
.chart-status-partial { color: #b78117; }
.trend-svg { display: block; width: 100%; height: 145px; margin-top: 10px; overflow: visible; }
.grid-line { stroke: var(--line); stroke-width: 1; }
.zero-line { stroke: #c8a84d; stroke-dasharray: 4 4; stroke-width: 1; }
.trend-line { fill: none; stroke: var(--blue); stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.5; vector-effect: non-scaling-stroke; }
.trend-dot { fill: var(--blue); stroke: var(--card); stroke-width: 1.5; }
.chart-range { display: flex; justify-content: space-between; color: var(--muted); font-size: 10px; font-variant-numeric: tabular-nums; }
.chart-empty { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 145px; color: var(--muted); font-size: 12px; }
</style>
