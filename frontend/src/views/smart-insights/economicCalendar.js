const IMPACTS = new Set(['high', 'medium', 'low'])
const CJK_PATTERN = /[\u3400-\u9fff]/u

export const DEFAULT_ECONOMIC_CALENDAR_FILTER = Object.freeze({
  timePreset: 'thisWeek',
  countries: Object.freeze(['US', 'VN']),
  impacts: Object.freeze([]),
  customStart: '',
  customEnd: ''
})

const VIETNAMESE_EVENT_EXACT = new Map([
  ['美国cpi年率', 'CPI Hoa Kỳ (theo năm)'],
  ['美国cpi月率', 'CPI Hoa Kỳ (theo tháng)'],
  ['us cpi y/y', 'CPI Hoa Kỳ (theo năm)'],
  ['us cpi m/m', 'CPI Hoa Kỳ (theo tháng)'],
  ['美国非农就业数据', 'Việc làm phi nông nghiệp Hoa Kỳ'],
  ['us non-farm payrolls', 'Việc làm phi nông nghiệp Hoa Kỳ'],
  ['non farm payrolls', 'Việc làm phi nông nghiệp Hoa Kỳ'],
  ['nonfarm payrolls', 'Việc làm phi nông nghiệp Hoa Kỳ'],
  ['美国初请失业金人数', 'Số đơn xin trợ cấp thất nghiệp lần đầu của Hoa Kỳ'],
  ['initial jobless claims', 'Số đơn xin trợ cấp thất nghiệp lần đầu'],
  ['美联储利率决议', 'Quyết định lãi suất Fed'],
  ['fed interest rate decision', 'Quyết định lãi suất Fed'],
  ['美联储联邦基金利率', 'Lãi suất quỹ liên bang của Fed'],
  ['federal funds rate', 'Lãi suất quỹ liên bang'],
  ['芝加哥联储全国活动指数', 'Chỉ số hoạt động quốc gia của Fed chi nhánh Chicago'],
  ['chicago fed national activity index', 'Chỉ số hoạt động quốc gia của Fed chi nhánh Chicago'],
  ['3个月国债拍卖', 'Đấu giá Hối phiếu 3 tháng'],
  ['6个月国债拍卖', 'Đấu giá Hối phiếu 6 tháng'],
  ['3-month bill auction', 'Đấu giá Hối phiếu 3 tháng'],
  ['6-month bill auction', 'Đấu giá Hối phiếu 6 tháng'],
  ['adp就业变化', 'Thay đổi việc làm của ADP'],
  ['adp employment change', 'Thay đổi việc làm của ADP'],
  ['红皮书年率', 'Chỉ số Redbook (theo năm)'],
  ['redbook y/y', 'Chỉ số Redbook (theo năm)'],
  ['建筑许可', 'Giấy phép xây dựng'],
  ['building permits', 'Giấy phép xây dựng'],
  ['房价指数', 'Chỉ số giá nhà'],
  ['新屋销售', 'Doanh số bán nhà mới'],
  ['new home sales', 'Doanh số bán nhà mới'],
  ['消费者信心', 'Niềm tin tiêu dùng'],
  ['consumer confidence', 'Niềm tin tiêu dùng'],
  ['零售销售', 'Doanh số bán lẻ'],
  ['retail sales', 'Doanh số bán lẻ'],
  ['工业产出', 'Sản lượng công nghiệp'],
  ['industrial production', 'Sản lượng công nghiệp'],
  ['贸易帐', 'Cán cân thương mại'],
  ['trade balance', 'Cán cân thương mại']
])

const VIETNAMESE_EVENT_PATTERNS = [
  [/^美国cpi.*年率/iu, 'CPI Hoa Kỳ (theo năm)'],
  [/^美国cpi.*月率/iu, 'CPI Hoa Kỳ (theo tháng)'],
  [/cpi.*(?:yoy|y\/y|year)/iu, 'Chỉ số CPI (theo năm)'],
  [/cpi.*(?:mom|m\/m|month)/iu, 'Chỉ số CPI (theo tháng)'],
  [/芝加哥联储.*活动/iu, 'Chỉ số hoạt động của Fed chi nhánh Chicago'],
  [/3\s*个月.*(?:国债|拍卖)/iu, 'Đấu giá Hối phiếu 3 tháng'],
  [/6\s*个月.*(?:国债|拍卖)/iu, 'Đấu giá Hối phiếu 6 tháng'],
  [/adp.*(?:就业|employment)/iu, 'Thay đổi việc làm của ADP'],
  [/红皮书.*年率/iu, 'Chỉ số Redbook (theo năm)'],
  [/标普.*房价指数.*年率/iu, 'Chỉ số giá nhà tổng hợp S&P/CS (theo năm)'],
  [/建筑许可.*月率/iu, 'Giấy phép xây dựng (theo tháng)'],
  [/建筑许可/iu, 'Giấy phép xây dựng'],
  [/房价指数.*年率/iu, 'Chỉ số giá nhà (theo năm)'],
  [/房价指数/iu, 'Chỉ số giá nhà'],
  [/新屋销售/iu, 'Doanh số bán nhà mới'],
  [/消费者信心/iu, 'Niềm tin tiêu dùng'],
  [/美联储.*利率|联邦基金利率/iu, 'Quyết định/lãi suất Fed'],
  [/初请失业金/iu, 'Số đơn xin trợ cấp thất nghiệp lần đầu'],
  [/非农/iu, 'Việc làm phi nông nghiệp'],
  [/失业率/iu, 'Tỷ lệ thất nghiệp'],
  [/零售销售/iu, 'Doanh số bán lẻ'],
  [/工业产出/iu, 'Sản lượng công nghiệp'],
  [/贸易帐/iu, 'Cán cân thương mại'],
  [/讲话|发言/iu, 'Phát biểu'],
  [/^building permits?/iu, 'Giấy phép xây dựng'],
  [/^new home sales/iu, 'Doanh số bán nhà mới'],
  [/^consumer confidence/iu, 'Niềm tin tiêu dùng'],
  [/^retail sales/iu, 'Doanh số bán lẻ'],
  [/^industrial production/iu, 'Sản lượng công nghiệp'],
  [/^trade balance/iu, 'Cán cân thương mại'],
  [/^fed speech|^fed remarks|^fed testimony/iu, 'Phát biểu của Fed'],
  [/^3[- ]month bill auction/iu, 'Đấu giá Hối phiếu 3 tháng'],
  [/^6[- ]month bill auction/iu, 'Đấu giá Hối phiếu 6 tháng'],
  [/^us non[- ]?farm payrolls?/iu, 'Việc làm phi nông nghiệp Hoa Kỳ'],
  [/^initial jobless claims/iu, 'Số đơn xin trợ cấp thất nghiệp lần đầu'],
  [/^federal funds rate/iu, 'Lãi suất quỹ liên bang'],
  [/^fed interest rate decision/iu, 'Quyết định lãi suất Fed'],
  [/^chicago fed national activity index/iu, 'Chỉ số hoạt động quốc gia của Fed chi nhánh Chicago']
]

const ENGLISH_EVENT_EXACT = new Map([
  ['美国cpi年率', 'US CPI (YoY)'],
  ['美国cpi月率', 'US CPI (MoM)'],
  ['us cpi y/y', 'US CPI (YoY)'],
  ['us cpi m/m', 'US CPI (MoM)'],
  ['美国非农就业数据', 'US Non-Farm Payrolls'],
  ['us non-farm payrolls', 'US Non-Farm Payrolls'],
  ['non farm payrolls', 'Non-Farm Payrolls'],
  ['nonfarm payrolls', 'Non-Farm Payrolls'],
  ['美国初请失业金人数', 'US Initial Jobless Claims'],
  ['initial jobless claims', 'Initial Jobless Claims'],
  ['美联储利率决议', 'Fed Interest Rate Decision'],
  ['fed interest rate decision', 'Fed Interest Rate Decision'],
  ['美联储联邦基金利率', 'Federal Funds Rate'],
  ['federal funds rate', 'Federal Funds Rate'],
  ['芝加哥联储全国活动指数', 'Chicago Fed National Activity Index'],
  ['chicago fed national activity index', 'Chicago Fed National Activity Index'],
  ['3个月国债拍卖', '3-Month Bill Auction'],
  ['6个月国债拍卖', '6-Month Bill Auction'],
  ['3-month bill auction', '3-Month Bill Auction'],
  ['6-month bill auction', '6-Month Bill Auction'],
  ['adp就业变化', 'ADP Employment Change'],
  ['adp employment change', 'ADP Employment Change'],
  ['红皮书年率', 'Redbook (YoY)'],
  ['redbook y/y', 'Redbook (YoY)'],
  ['建筑许可', 'Building Permits'],
  ['building permits', 'Building Permits'],
  ['房价指数', 'House Price Index'],
  ['新屋销售', 'New Home Sales'],
  ['new home sales', 'New Home Sales'],
  ['消费者信心', 'Consumer Confidence'],
  ['consumer confidence', 'Consumer Confidence'],
  ['零售销售', 'Retail Sales'],
  ['retail sales', 'Retail Sales'],
  ['工业产出', 'Industrial Production'],
  ['industrial production', 'Industrial Production'],
  ['贸易帐', 'Trade Balance'],
  ['trade balance', 'Trade Balance']
])

const ENGLISH_EVENT_PATTERNS = [
  [/^美国cpi.*年率/iu, 'US CPI (YoY)'],
  [/^美国cpi.*月率/iu, 'US CPI (MoM)'],
  [/cpi.*(?:yoy|y\/y|year)/iu, 'CPI (YoY)'],
  [/cpi.*(?:mom|m\/m|month)/iu, 'CPI (MoM)'],
  [/芝加哥联储.*活动/iu, 'Chicago Fed National Activity Index'],
  [/3\s*个月.*(?:国债|拍卖)/iu, '3-Month Bill Auction'],
  [/6\s*个月.*(?:国债|拍卖)/iu, '6-Month Bill Auction'],
  [/adp.*(?:就业|employment)/iu, 'ADP Employment Change'],
  [/红皮书.*年率/iu, 'Redbook (YoY)'],
  [/标普.*房价指数.*年率/iu, 'S&P/CS House Price Index (YoY)'],
  [/建筑许可.*月率/iu, 'Building Permits (MoM)'],
  [/建筑许可/iu, 'Building Permits'],
  [/房价指数.*年率/iu, 'House Price Index (YoY)'],
  [/房价指数/iu, 'House Price Index'],
  [/新屋销售/iu, 'New Home Sales'],
  [/消费者信心/iu, 'Consumer Confidence'],
  [/美联储.*利率|联邦基金利率/iu, 'Fed Interest Rate Decision'],
  [/初请失业金/iu, 'Initial Jobless Claims'],
  [/非农/iu, 'Non-Farm Payrolls'],
  [/失业率/iu, 'Unemployment Rate'],
  [/零售销售/iu, 'Retail Sales'],
  [/工业产出/iu, 'Industrial Production'],
  [/贸易帐/iu, 'Trade Balance'],
  [/讲话|发言/iu, 'Speech'],
  [/^building permits?/iu, 'Building Permits'],
  [/^new home sales/iu, 'New Home Sales'],
  [/^consumer confidence/iu, 'Consumer Confidence'],
  [/^retail sales/iu, 'Retail Sales'],
  [/^industrial production/iu, 'Industrial Production'],
  [/^trade balance/iu, 'Trade Balance'],
  [/^fed speech|^fed remarks|^fed testimony/iu, 'Fed Speech'],
  [/^3[- ]month bill auction/iu, '3-Month Bill Auction'],
  [/^6[- ]month bill auction/iu, '6-Month Bill Auction'],
  [/^us non[- ]?farm payrolls?/iu, 'US Non-Farm Payrolls'],
  [/^initial jobless claims/iu, 'Initial Jobless Claims'],
  [/^federal funds rate/iu, 'Federal Funds Rate'],
  [/^fed interest rate decision/iu, 'Fed Interest Rate Decision'],
  [/^chicago fed national activity index/iu, 'Chicago Fed National Activity Index']
]

function textValue (value) {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  return text && text !== '-' ? text : null
}

function normalizedEventName (value) {
  return (textValue(value) || '').replace(/\s+/gu, ' ').toLowerCase()
}

function isVietnameseLocale (locale) {
  return String(locale || '').toLowerCase().startsWith('vi')
}

function isChineseLocale (locale) {
  return String(locale || '').toLowerCase().startsWith('zh')
}

function translateVietnameseEventName (value) {
  const source = textValue(value)
  if (!source) return null

  const exact = VIETNAMESE_EVENT_EXACT.get(normalizedEventName(source))
  if (exact) return exact

  for (const [pattern, translation] of VIETNAMESE_EVENT_PATTERNS) {
    if (pattern.test(source)) return translation
  }

  return null
}

function translateEnglishEventName (value) {
  const source = textValue(value)
  if (!source) return null

  const exact = ENGLISH_EVENT_EXACT.get(normalizedEventName(source))
  if (exact) return exact

  for (const [pattern, translation] of ENGLISH_EVENT_PATTERNS) {
    if (pattern.test(source)) return translation
  }

  return null
}

function eventSourceName (event) {
  return textValue(event && (event.name || event.event || event.name_en || event.event_en)) || ''
}

function eventEnglishName (event) {
  return textValue(event && (event.name_en || event.event_en || event.event || event.name)) || ''
}

function localizeEventName (event, locale) {
  const explicitVietnamese = textValue(event && (event.name_vi || event.event_vi))
  const sourceName = eventSourceName(event)
  const source = explicitVietnamese || sourceName
  const englishName = eventEnglishName(event)

  if (isChineseLocale(locale)) return sourceName || englishName

  if (!isVietnameseLocale(locale)) {
    const translatedEnglish = translateEnglishEventName(sourceName) || translateEnglishEventName(englishName)
    if (translatedEnglish) return translatedEnglish
    if (englishName && !CJK_PATTERN.test(englishName)) return englishName
    if (sourceName && !CJK_PATTERN.test(sourceName)) return sourceName
    return CJK_PATTERN.test(sourceName || englishName) ? 'Economic event' : (sourceName || englishName)
  }

  const translated = translateVietnameseEventName(source)
  if (translated) return translated
  if (explicitVietnamese && !CJK_PATTERN.test(explicitVietnamese)) return explicitVietnamese

  const translatedEnglish = translateVietnameseEventName(englishName)
  if (translatedEnglish) return translatedEnglish
  if (englishName && !CJK_PATTERN.test(englishName)) return englishName
  return CJK_PATTERN.test(source) ? 'Sự kiện kinh tế' : source
}

function normalizeImpact (value) {
  const text = String(value || '').toLowerCase()
  if (['3', '4', 'critical', 'high', 'h'].includes(text)) return 'high'
  if (['1', 'low', 'l'].includes(text)) return 'low'
  if (['2', 'medium', 'moderate', 'm'].includes(text)) return 'medium'
  return 'medium'
}

function eventDate (event) {
  const raw = event && (event.date || event.eventDate || event.event_date)
  if (raw) return String(raw).slice(0, 10)
  const eventAt = event && (event.eventAt || event.event_at)
  if (!eventAt) return ''
  const date = new Date(eventAt)
  return Number.isNaN(date.getTime()) ? '' : date.toISOString().slice(0, 10)
}

function eventTime (event) {
  const raw = event && (event.time || event.eventTime || event.event_time)
  if (raw) {
    const match = String(raw).match(/(\d{1,2}):(\d{2})/u)
    if (match) return `${match[1].padStart(2, '0')}:${match[2]}`
  }
  const eventAt = event && (event.eventAt || event.event_at)
  if (!eventAt) return ''
  const date = new Date(eventAt)
  if (Number.isNaN(date.getTime())) return ''
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function sortEvents (events) {
  return events.slice().sort((left, right) => {
    const dateOrder = String(left.date || '').localeCompare(String(right.date || ''))
    if (dateOrder) return dateOrder
    return String(left.time || '99:99').localeCompare(String(right.time || '99:99'))
  })
}

function localDate (value) {
  const date = value instanceof Date ? new Date(value.getTime()) : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function addDays (date, days) {
  const result = new Date(date.getTime())
  result.setDate(result.getDate() + days)
  return result
}

function dateKey (date) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
}

function dateKeyValue (value) {
  const text = textValue(value)
  if (!text) return ''
  if (/^\d{4}-\d{2}-\d{2}$/u.test(text)) return text
  const date = localDate(text)
  return date ? dateKey(date) : ''
}

export function getEconomicCalendarDateRange (preset = 'thisWeek', referenceDate = new Date(), customStart = '', customEnd = '') {
  const today = localDate(referenceDate) || localDate(new Date())
  const normalizedPreset = String(preset || 'thisWeek')
  const weekday = today.getDay()
  const weekStart = addDays(today, weekday === 0 ? -6 : 1 - weekday)

  if (normalizedPreset === 'custom') {
    const start = dateKeyValue(customStart)
    const end = dateKeyValue(customEnd || customStart)
    if (!start && !end) return null
    if (!start || !end) return { start: start || end, end: end || start }
    return start <= end ? { start, end } : { start: end, end: start }
  }
  if (normalizedPreset === 'yesterday') {
    const yesterday = dateKey(addDays(today, -1))
    return { start: yesterday, end: yesterday }
  }
  if (normalizedPreset === 'thisWeek') return { start: dateKey(weekStart), end: dateKey(addDays(weekStart, 6)) }
  if (normalizedPreset === 'nextWeek') {
    const nextWeekStart = addDays(weekStart, 7)
    return { start: dateKey(nextWeekStart), end: dateKey(addDays(nextWeekStart, 6)) }
  }
  const todayKey = dateKey(today)
  return { start: todayKey, end: todayKey }
}

export function normalizeEconomicCalendarEvents (events = [], locale = 'en-US') {
  return sortEvents((Array.isArray(events) ? events : []).map((event, index) => ({
    id: event && event.id != null ? event.id : `${eventDate(event)}-${eventTime(event)}-${index}`,
    name: localizeEventName(event, locale),
    country: textValue(event && (event.country || event.region)) || 'INTL',
    date: eventDate(event),
    time: eventTime(event),
    impact: normalizeImpact(event && (event.importance || event.impact)),
    actual: textValue(event && event.actual),
    forecast: textValue(event && (event.forecast || event.estimate)),
    previous: textValue(event && (event.previous || event.prev)),
    surprise: textValue(event && (event.surprise || event.actual_impact))
  })).filter(event => event.name && event.date))
}

export function filterEconomicCalendarEvents (events = [], impact = 'all') {
  const normalizedImpact = String(impact || 'all').toLowerCase()
  if (!IMPACTS.has(normalizedImpact)) return events.slice()
  return events.filter(event => event.impact === normalizedImpact)
}

export function filterEconomicCalendarEventsByCriteria (events = [], criteria = {}, referenceDate = new Date()) {
  const options = { ...DEFAULT_ECONOMIC_CALENDAR_FILTER, ...(criteria || {}) }
  const countries = new Set((Array.isArray(options.countries) ? options.countries : []).map(country => String(country).toUpperCase()))
  const impacts = new Set((Array.isArray(options.impacts) ? options.impacts : []).map(impact => String(impact).toLowerCase()))
  const dateRange = getEconomicCalendarDateRange(options.timePreset, referenceDate, options.customStart, options.customEnd)

  return (Array.isArray(events) ? events : []).filter(event => {
    const country = String(event && event.country || '').toUpperCase()
    const impact = String(event && event.impact || '').toLowerCase()
    const date = dateKeyValue(event && event.date)
    const countryMatches = !countries.size || countries.has(country)
    const impactMatches = !impacts.size || impacts.has(impact)
    const dateMatches = !dateRange || (date >= dateRange.start && date <= dateRange.end)
    return countryMatches && impactMatches && dateMatches
  })
}

export function groupEconomicCalendarEvents (events = []) {
  const groups = []
  for (const event of sortEvents(events)) {
    const previous = groups[groups.length - 1]
    if (previous && previous.date === event.date) {
      previous.events.push(event)
    } else {
      groups.push({ date: event.date, events: [event] })
    }
  }
  return groups
}
