<template>
  <section class="economic-calendar" :aria-label="$t('smartInsights.calendarTitle')">
    <div class="economic-calendar-toolbar">
      <div>
        <h2>{{ $t('smartInsights.calendarTitle') }}</h2>
        <p>{{ $t('smartInsights.calendarDesc') }}</p>
      </div>
    </div>

    <div class="calendar-filter-panel" :aria-label="$t('smartInsights.calendarFilters')">
      <div class="calendar-time-filter">
        <span class="calendar-filter-label">{{ $t('smartInsights.calendarTimeRange') }}</span>
        <div class="calendar-filter-buttons" role="group" :aria-label="$t('smartInsights.calendarTimeRange')">
          <button
            v-for="option in timeOptions"
            :key="option.value"
            type="button"
            :class="{ active: timePreset === option.value }"
            :aria-pressed="timePreset === option.value"
            @click="selectTimePreset(option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <div class="calendar-select-filters">
        <label class="calendar-select-field">
          <span class="calendar-filter-label">{{ $t('smartInsights.calendarCountry') }}</span>
          <a-select
            v-model="selectedCountries"
            mode="multiple"
            size="small"
            :max-tag-count="2"
            :placeholder="$t('smartInsights.calendarAllCountries')"
            :aria-label="$t('smartInsights.calendarCountry')"
          >
            <a-select-option v-for="country in countryOptions" :key="country" :value="country">
              {{ country }}
            </a-select-option>
          </a-select>
        </label>

        <label class="calendar-select-field">
          <span class="calendar-filter-label">{{ $t('smartInsights.calendarImportance') }}</span>
          <a-select
            v-model="selectedImpacts"
            mode="multiple"
            size="small"
            :max-tag-count="2"
            :placeholder="$t('smartInsights.calendarAllImportance')"
            :aria-label="$t('smartInsights.calendarImportance')"
          >
            <a-select-option v-for="option in impactOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </a-select-option>
          </a-select>
        </label>
      </div>

      <div v-if="timePreset === 'custom'" class="calendar-custom-range">
        <label>
          <span>{{ $t('smartInsights.calendarFrom') }}</span>
          <input v-model="customStart" type="date" :aria-label="$t('smartInsights.calendarFrom')">
        </label>
        <span class="calendar-range-separator" aria-hidden="true">→</span>
        <label>
          <span>{{ $t('smartInsights.calendarTo') }}</span>
          <input v-model="customEnd" type="date" :aria-label="$t('smartInsights.calendarTo')">
        </label>
      </div>
    </div>

    <div class="economic-calendar-scroll">
      <table class="economic-calendar-table">
        <colgroup>
          <col class="calendar-col-time">
          <col class="calendar-col-currency">
          <col class="calendar-col-event">
          <col class="calendar-col-impact">
          <col class="calendar-col-value">
          <col class="calendar-col-value">
          <col class="calendar-col-value">
        </colgroup>
        <thead>
          <tr>
            <th scope="col">{{ $t('smartInsights.calendarTime') }}</th>
            <th scope="col">{{ $t('smartInsights.calendarCurrency') }}</th>
            <th scope="col">{{ $t('smartInsights.calendarEvent') }}</th>
            <th scope="col">{{ $t('smartInsights.calendarImportance') }}</th>
            <th scope="col">{{ $t('smartInsights.calendarActual') }}</th>
            <th scope="col">{{ $t('smartInsights.calendarForecast') }}</th>
            <th scope="col">{{ $t('smartInsights.calendarPrevious') }}</th>
          </tr>
        </thead>
        <tbody v-if="loading">
          <tr class="calendar-state-row">
            <td colspan="7"><a-spin size="small" /> {{ $t('smartInsights.calendarLoading') }}</td>
          </tr>
        </tbody>
        <tbody v-else-if="error">
          <tr class="calendar-state-row">
            <td colspan="7">{{ error }}</td>
          </tr>
        </tbody>
        <tbody v-else-if="!groupedEvents.length">
          <tr class="calendar-state-row">
            <td colspan="7">{{ $t('smartInsights.calendarEmpty') }}</td>
          </tr>
        </tbody>
        <tbody v-for="group in groupedEvents" v-else :key="group.date" class="calendar-day-group">
          <tr class="calendar-day-row">
            <th colspan="7" scope="rowgroup">{{ formatDay(group.date) }}</th>
          </tr>
          <tr v-for="event in group.events" :key="eventKey(event)" class="calendar-event-row">
            <td class="calendar-time">{{ event.time || '—' }}</td>
            <td class="calendar-currency">
              <Icon :icon="countryFlagIcon(event.country)" aria-hidden="true" />
              <span>{{ event.country }}</span>
            </td>
            <td class="calendar-event-name">
              <span>{{ event.name }}</span>
              <a-icon v-if="isSpeechEvent(event)" type="sound" class="calendar-speech" />
            </td>
            <td class="calendar-importance">
              <span class="importance-stars" :aria-label="impactLabel(event.impact)">
                <a-icon
                  v-for="index in 3"
                  :key="index"
                  type="star"
                  theme="filled"
                  :class="{ muted: index > impactScore(event.impact) }"
                />
              </span>
            </td>
            <td :class="['calendar-value', valueTone(event)]">{{ event.actual || '' }}</td>
            <td class="calendar-value">{{ event.forecast || '' }}</td>
            <td class="calendar-value">{{ event.previous || '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="hasMoreEvents" class="calendar-more">
      <button type="button" @click="toggleExpanded">
        {{ showAll ? $t('smartInsights.calendarCollapse') : $t('smartInsights.calendarShowMore') }}
      </button>
    </div>
  </section>
</template>

<script>
import { Icon } from '@iconify/vue2'
import { DEFAULT_ECONOMIC_CALENDAR_FILTER, filterEconomicCalendarEventsByCriteria, groupEconomicCalendarEvents, normalizeEconomicCalendarEvents } from '../economicCalendar'

const INITIAL_EVENT_LIMIT = 12

export default {
  name: 'EconomicCalendarTable',
  components: { Icon },
  props: {
    events: { type: Array, default: () => [] },
    filter: { type: Object, default: () => ({ ...DEFAULT_ECONOMIC_CALENDAR_FILTER }) },
    loading: { type: Boolean, default: false },
    error: { type: String, default: '' }
  },
  data () {
    return { showAll: false }
  },
  computed: {
    activeFilter () { return { ...DEFAULT_ECONOMIC_CALENDAR_FILTER, ...(this.filter || {}) } },
    normalizedEvents () { return normalizeEconomicCalendarEvents(this.events, this.$i18n && this.$i18n.locale) },
    filteredEvents () { return filterEconomicCalendarEventsByCriteria(this.normalizedEvents, this.activeFilter) },
    visibleEvents () { return this.showAll ? this.filteredEvents : this.filteredEvents.slice(0, INITIAL_EVENT_LIMIT) },
    groupedEvents () { return groupEconomicCalendarEvents(this.visibleEvents) },
    hasMoreEvents () { return this.filteredEvents.length > INITIAL_EVENT_LIMIT },
    timePreset: {
      get () { return this.activeFilter.timePreset },
      set (value) { this.updateFilter({ timePreset: value }) }
    },
    selectedCountries: {
      get () { return Array.isArray(this.activeFilter.countries) ? this.activeFilter.countries : [] },
      set (value) { this.updateFilter({ countries: Array.isArray(value) ? value : [] }) }
    },
    selectedImpacts: {
      get () { return Array.isArray(this.activeFilter.impacts) ? this.activeFilter.impacts : [] },
      set (value) { this.updateFilter({ impacts: Array.isArray(value) ? value : [] }) }
    },
    customStart: {
      get () { return this.activeFilter.customStart || '' },
      set (value) { this.updateFilter({ customStart: value || '' }) }
    },
    customEnd: {
      get () { return this.activeFilter.customEnd || '' },
      set (value) { this.updateFilter({ customEnd: value || '' }) }
    },
    timeOptions () {
      return [
        { value: 'yesterday', label: this.$t('smartInsights.calendarYesterday') },
        { value: 'today', label: this.$t('smartInsights.calendarToday') },
        { value: 'thisWeek', label: this.$t('smartInsights.calendarThisWeek') },
        { value: 'nextWeek', label: this.$t('smartInsights.calendarNextWeek') },
        { value: 'custom', label: this.$t('smartInsights.calendarCustom') }
      ]
    },
    countryOptions () {
      const countries = new Set(DEFAULT_ECONOMIC_CALENDAR_FILTER.countries)
      this.normalizedEvents.forEach(event => countries.add(String(event.country || '').toUpperCase()))
      return Array.from(countries).filter(Boolean)
    },
    impactOptions () {
      return [
        { value: 'high', label: this.$t('smartInsights.high') },
        { value: 'medium', label: this.$t('smartInsights.medium') },
        { value: 'low', label: this.$t('smartInsights.low') }
      ]
    },
    isVietnamese () { return this.$i18n && String(this.$i18n.locale || '').toLowerCase().startsWith('vi') }
  },
  watch: {
    filter: { deep: true, handler () { this.showAll = false } }
  },
  methods: {
    updateFilter (patch) {
      this.showAll = false
      this.$emit('filter-change', { ...this.activeFilter, ...patch })
    },
    selectTimePreset (value) { this.timePreset = value },
    toggleExpanded () { this.showAll = !this.showAll },
    formatDay (dateValue) {
      const date = new Date(`${dateValue}T00:00:00`)
      if (Number.isNaN(date.getTime())) return dateValue
      return date.toLocaleDateString(this.isVietnamese ? 'vi-VN' : 'en-US', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
    },
    eventKey (event) { return `${event.date}-${event.time}-${event.country}-${event.name}` },
    impactScore (impact) { return { high: 3, medium: 2, low: 1 }[impact] || 1 },
    impactLabel (impact) {
      return {
        high: this.$t('smartInsights.high'),
        medium: this.$t('smartInsights.medium'),
        low: this.$t('smartInsights.low')
      }[impact] || this.$t('smartInsights.low')
    },
    countryFlagIcon (country) {
      const icons = {
        US: 'flag:us-4x3',
        EU: 'flag:eu-4x3',
        GB: 'flag:gb-4x3',
        UK: 'flag:gb-4x3',
        CN: 'flag:cn-4x3',
        JP: 'flag:jp-4x3',
        VN: 'flag:vn-4x3',
        AU: 'flag:au-4x3',
        CA: 'flag:ca-4x3'
      }
      return icons[String(country || '').toUpperCase()] || 'flag:un-4x3'
    },
    isSpeechEvent (event) { return /speech|remarks|testimony|phát biểu/u.test(String(event && event.name || '').toLowerCase()) },
    valueTone (event) {
      const surprise = String(event && event.surprise || '').toLowerCase()
      if (['positive', 'bullish', 'better', 'above'].includes(surprise)) return 'calendar-value--positive'
      if (['negative', 'bearish', 'worse', 'below'].includes(surprise)) return 'calendar-value--negative'
      return ''
    }
  }
}
</script>

<style lang="less" scoped>
.economic-calendar { margin-top: 18px; overflow: hidden; border: 1px solid var(--line); border-radius: 10px; color: var(--ink); background: var(--card); }
.economic-calendar-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 15px 17px; border-bottom: 1px solid var(--line); }
.economic-calendar-toolbar h2 { margin: 0; color: var(--ink); font-size: 16px; line-height: 1.3; }
.economic-calendar-toolbar p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
.calendar-filter-panel { display: grid; gap: 12px; padding: 14px 17px; border-bottom: 1px solid var(--line); background: var(--page-bg); }
.calendar-time-filter { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.calendar-filter-label { color: var(--ink); font-size: 12px; font-weight: 700; white-space: nowrap; }
.calendar-filter-buttons { display: flex; flex-wrap: wrap; gap: 5px; }
.calendar-filter-buttons button, .calendar-more button { padding: 5px 10px; border: 1px solid var(--line); border-radius: 5px; color: var(--muted); background: var(--card); font-size: 12px; cursor: pointer; }
.calendar-filter-buttons button:hover, .calendar-filter-buttons button:focus-visible, .calendar-filter-buttons button.active, .calendar-more button:hover, .calendar-more button:focus-visible { border-color: var(--blue); color: var(--blue); background: var(--soft-blue); outline: none; }
.calendar-select-filters { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.calendar-select-field { display: grid; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: 8px; min-width: 0; }
.calendar-select-field .ant-select { width: 100%; min-width: 0; }
.calendar-custom-range { display: flex; align-items: end; flex-wrap: wrap; gap: 10px; }
.calendar-custom-range label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; font-weight: 600; }
.calendar-custom-range input { min-height: 30px; padding: 4px 8px; border: 1px solid var(--line); border-radius: 5px; color: var(--ink); background: var(--card); font: inherit; }
.calendar-range-separator { padding-bottom: 6px; color: var(--muted); font-size: 16px; }
.economic-calendar-scroll { width: 100%; overflow-x: auto; }
.economic-calendar-table { width: 100%; min-width: 760px; border-collapse: collapse; table-layout: fixed; font-size: 14px; }
.economic-calendar-table th, .economic-calendar-table td { border-bottom: 1px solid var(--line); }
.economic-calendar-table thead th { height: 40px; padding: 0 8px; color: var(--ink); font-size: 13px; font-weight: 600; text-align: left; white-space: nowrap; }
.economic-calendar-table thead th:nth-child(n+4), .economic-calendar-table td:nth-child(n+4) { text-align: center; }
.calendar-col-time { width: 72px; }.calendar-col-currency { width: 76px; }.calendar-col-event { width: auto; }.calendar-col-impact { width: 118px; }.calendar-col-value { width: 105px; }
.calendar-day-row th { height: 40px; padding: 0 10px; color: var(--ink); background: var(--page-bg); font-size: 14px; font-weight: 700; text-align: center; }
.calendar-event-row td { min-height: 39px; padding: 8px; color: var(--ink); vertical-align: middle; }
.calendar-event-row:hover td { background: var(--soft-blue); }
.calendar-time { font-variant-numeric: tabular-nums; white-space: nowrap; }.calendar-currency { display: flex; align-items: center; gap: 7px; white-space: nowrap; }.calendar-currency .iconify { width: 17px; height: 12px; flex: 0 0 auto; }.calendar-event-name { overflow-wrap: anywhere; line-height: 1.4; }.calendar-speech { margin-left: 7px; color: var(--muted); }
.calendar-importance { white-space: nowrap; }.importance-stars { display: inline-flex; gap: 2px; color: #a8afb8; }.importance-stars .muted { color: #dce0e5; }.calendar-value { font-variant-numeric: tabular-nums; white-space: nowrap; }.calendar-value--positive { color: #159447 !important; font-weight: 600; }.calendar-value--negative { color: #f04438 !important; font-weight: 600; }
.calendar-state-row td { height: 100px; color: var(--muted); text-align: center; }.calendar-state-row .ant-spin { margin-right: 7px; }
.calendar-more { display: flex; justify-content: center; padding: 12px; border-top: 1px solid var(--line); }
.theme-dark .economic-calendar { border-color: var(--line); }.theme-dark .calendar-filter-panel { background: var(--page-bg); }.theme-dark .calendar-custom-range input { color: var(--ink); background: var(--card); }.theme-dark .calendar-event-row:hover td { background: var(--soft-blue); }
@media (max-width: 680px) { .economic-calendar-toolbar { align-items: flex-start; flex-direction: column; }.calendar-select-filters { grid-template-columns: 1fr; }.calendar-select-field { grid-template-columns: 100px minmax(0, 1fr); }.economic-calendar-table { min-width: 720px; } }
</style>
