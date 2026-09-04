import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const pageSource = fs.readFileSync(new URL('../../src/views/smart-insights/index.vue', import.meta.url), 'utf8')
const calendarComponentSource = fs.readFileSync(new URL('../../src/views/smart-insights/components/EconomicCalendarTable.vue', import.meta.url), 'utf8')
const calendarModule = await import('../../src/views/smart-insights/economicCalendar.js').catch(() => null)

test('Smart Insights renders the API-backed economic calendar table with a real impact filter', () => {
  assert.match(pageSource, /getEconomicCalendar/u)
  assert.match(pageSource, /calendarEvents/u)
  assert.match(pageSource, /<economic-calendar-table/u)
  assert.match(pageSource, /calendarFilter:\s*\{[\s\S]*timePreset:\s*'thisWeek'/u)
  assert.match(pageSource, /countries:\s*\['US',\s*'VN'\]/u)
  assert.match(pageSource, /impacts:\s*\[\]/u)
  assert.match(calendarComponentSource, /normalizeEconomicCalendarEvents\(this\.events, this\.\$i18n && this\.\$i18n\.locale\)/u)
  assert.match(calendarComponentSource, /calendarShowMore/u)
  assert.match(calendarComponentSource, /mode="multiple"/u)
})

test('economic calendar normalizes provider rows into the table model and sorts by date/time', () => {
  assert.ok(calendarModule)
  assert.equal(typeof calendarModule.normalizeEconomicCalendarEvents, 'function')
  assert.deepEqual(calendarModule.normalizeEconomicCalendarEvents([
    {
      id: 'later',
      name_en: 'Retail Sales',
      country: 'US',
      date: '2026-08-25',
      time: '19:30',
      importance: 'high',
      actual: '1.4%',
      forecast: '1.2%',
      previous: '1.3%',
      actual_impact: 'bearish'
    },
    {
      id: 'earlier',
      name_en: 'Fed Speech',
      country: 'US',
      date: '2026-08-24',
      time: '09:00',
      importance: 'low',
      actual: null,
      forecast: null,
      previous: null
    }
  ]), [
    {
      id: 'earlier',
      name: 'Fed Speech',
      country: 'US',
      date: '2026-08-24',
      time: '09:00',
      impact: 'low',
      actual: null,
      forecast: null,
      previous: null,
      surprise: null
    },
    {
      id: 'later',
      name: 'Retail Sales',
      country: 'US',
      date: '2026-08-25',
      time: '19:30',
      impact: 'high',
      actual: '1.4%',
      forecast: '1.2%',
      previous: '1.3%',
      surprise: 'bearish'
    }
  ])
})

test('economic calendar renders provider instants in Vietnam time', () => {
  const normalized = calendarModule.normalizeEconomicCalendarEvents([{
    id: 'utc-event',
    eventAt: '2026-09-04T20:30:00Z',
    name: 'US CPI y/y',
    country: 'US',
    impact: 'high'
  }], 'vi-VN')

  assert.deepEqual(normalized[0], {
    id: 'utc-event',
    name: 'CPI Hoa Kỳ (theo năm)',
    country: 'US',
    date: '2026-09-05',
    time: '03:30',
    impact: 'high',
    actual: null,
    forecast: null,
    previous: null,
    surprise: null
  })
})

test('economic calendar localizes Chinese provider event names for Vietnamese users', () => {
  assert.ok(calendarModule)
  const normalized = calendarModule.normalizeEconomicCalendarEvents([
    {
      id: 'cpi',
      name: '美国CPI年率',
      name_en: '美国CPI年率',
      country: 'US',
      date: '2026-08-25',
      time: '19:30',
      importance: 'high'
    },
    {
      id: 'permits',
      name_en: 'Building Permits',
      country: 'US',
      date: '2026-08-25',
      time: '20:00',
      importance: 'medium'
    }
  ], 'vi-VN')

  assert.equal(normalized[0].name, 'CPI Hoa Kỳ (theo năm)')
  assert.equal(normalized[1].name, 'Giấy phép xây dựng')
  assert.doesNotMatch(normalized[0].name, /[\u3400-\u9fff]/u)
  assert.doesNotMatch(normalized[1].name, /[\u3400-\u9fff]/u)
})

test('economic calendar localizes Chinese provider event names for English users and preserves Chinese locale', () => {
  assert.ok(calendarModule)
  const sourceEvent = {
    id: 'permits',
    name: '美国建筑许可月率',
    name_en: '美国建筑许可月率',
    country: 'US',
    date: '2026-08-25',
    time: '19:30',
    importance: 'high'
  }

  const english = calendarModule.normalizeEconomicCalendarEvents([sourceEvent], 'en-US')
  const chinese = calendarModule.normalizeEconomicCalendarEvents([sourceEvent], 'zh-CN')

  assert.equal(english[0].name, 'Building Permits (MoM)')
  assert.doesNotMatch(english[0].name, /[\u3400-\u9fff]/u)
  assert.equal(chinese[0].name, '美国建筑许可月率')
})

test('economic calendar does not leak unknown Chinese provider labels in English or Vietnamese', () => {
  assert.ok(calendarModule)
  const sourceEvent = {
    id: 'unknown',
    name: '美国未知指标',
    name_en: '美国未知指标',
    country: 'US',
    date: '2026-08-25',
    time: '19:30',
    importance: 'low'
  }

  const english = calendarModule.normalizeEconomicCalendarEvents([sourceEvent], 'en-US')
  const vietnamese = calendarModule.normalizeEconomicCalendarEvents([sourceEvent], 'vi-VN')

  assert.equal(english[0].name, 'Economic event')
  assert.equal(vietnamese[0].name, 'Sự kiện kinh tế')
  assert.doesNotMatch(english[0].name, /[\u3400-\u9fff]/u)
  assert.doesNotMatch(vietnamese[0].name, /[\u3400-\u9fff]/u)
})

test('economic calendar filters by impact without mutating the normalized list', () => {
  assert.ok(calendarModule)
  assert.equal(typeof calendarModule.filterEconomicCalendarEvents, 'function')
  const events = [
    { id: 'high', impact: 'high' },
    { id: 'medium', impact: 'medium' },
    { id: 'low', impact: 'low' }
  ]
  assert.deepEqual(calendarModule.filterEconomicCalendarEvents(events, 'high'), [{ id: 'high', impact: 'high' }])
  assert.deepEqual(calendarModule.filterEconomicCalendarEvents(events, 'all'), events)
  assert.deepEqual(events, [
    { id: 'high', impact: 'high' },
    { id: 'medium', impact: 'medium' },
    { id: 'low', impact: 'low' }
  ])
})

test('economic calendar groups sorted events into date sections', () => {
  assert.ok(calendarModule)
  assert.equal(typeof calendarModule.groupEconomicCalendarEvents, 'function')
  assert.deepEqual(calendarModule.groupEconomicCalendarEvents([
    { id: 'b', date: '2026-08-25', time: '10:00' },
    { id: 'a', date: '2026-08-25', time: '09:00' },
    { id: 'c', date: '2026-08-26', time: '09:00' }
  ]), [
    { date: '2026-08-25', events: [{ id: 'a', date: '2026-08-25', time: '09:00' }, { id: 'b', date: '2026-08-25', time: '10:00' }] },
    { date: '2026-08-26', events: [{ id: 'c', date: '2026-08-26', time: '09:00' }] }
  ])
})

test('economic calendar filters by date preset, multiple countries, and multiple impacts', () => {
  assert.ok(calendarModule)
  assert.equal(typeof calendarModule.filterEconomicCalendarEventsByCriteria, 'function')
  const events = [
    { id: 'yesterday-us', date: '2026-08-25', country: 'US', impact: 'high' },
    { id: 'today-us', date: '2026-08-26', country: 'US', impact: 'low' },
    { id: 'today-vn', date: '2026-08-26', country: 'VN', impact: 'high' },
    { id: 'today-eu', date: '2026-08-26', country: 'EU', impact: 'medium' },
    { id: 'this-week-vn', date: '2026-08-24', country: 'VN', impact: 'medium' },
    { id: 'next-week-us', date: '2026-08-31', country: 'US', impact: 'high' }
  ]
  const referenceDate = new Date('2026-08-26T12:00:00')

  assert.deepEqual(calendarModule.getEconomicCalendarDateRange(undefined, referenceDate), { start: '2026-08-24', end: '2026-08-30' })
  assert.deepEqual(calendarModule.filterEconomicCalendarEventsByCriteria(events, undefined, referenceDate).map(event => event.id), ['yesterday-us', 'today-us', 'today-vn', 'this-week-vn'])
  assert.deepEqual(calendarModule.filterEconomicCalendarEventsByCriteria(events, { timePreset: 'yesterday', countries: ['US', 'VN'], impacts: [] }, referenceDate).map(event => event.id), ['yesterday-us'])
  assert.deepEqual(calendarModule.filterEconomicCalendarEventsByCriteria(events, { timePreset: 'today', countries: ['US', 'VN'], impacts: ['high', 'medium'] }, referenceDate).map(event => event.id), ['today-vn'])
  assert.deepEqual(calendarModule.filterEconomicCalendarEventsByCriteria(events, { timePreset: 'thisWeek', countries: ['VN'], impacts: [] }, referenceDate).map(event => event.id), ['today-vn', 'this-week-vn'])
  assert.deepEqual(calendarModule.filterEconomicCalendarEventsByCriteria(events, { timePreset: 'nextWeek', countries: ['US'], impacts: ['high'] }, referenceDate).map(event => event.id), ['next-week-us'])
  assert.deepEqual(calendarModule.filterEconomicCalendarEventsByCriteria(events, { timePreset: 'custom', countries: ['US', 'VN'], impacts: [], customStart: '2026-08-25', customEnd: '2026-08-26' }, referenceDate).map(event => event.id), ['yesterday-us', 'today-us', 'today-vn'])
})

test('economic calendar limits long result sets and exposes a show-more contract', () => {
  assert.match(calendarComponentSource, /INITIAL_EVENT_LIMIT\s*=\s*12/u)
  assert.match(calendarComponentSource, /hasMoreEvents/u)
  assert.match(calendarComponentSource, /showAll/u)
  assert.match(calendarComponentSource, /calendarCollapse/u)
})
