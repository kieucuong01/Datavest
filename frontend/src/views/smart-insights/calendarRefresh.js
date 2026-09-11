export function calendarCacheFresh (cache, now = Date.now()) {
  return Number.isFinite(cache && cache.loadedAt) && now >= cache.loadedAt && now - cache.loadedAt < 300000
}

export function calendarMissingValue (event, field, vietnamese, now = Date.now()) {
  if (field !== 'actual') return vietnamese ? 'Nguồn chưa cung cấp' : 'Not provided'
  const scheduled = /^\d{2}:\d{2}$/.test(event.time || '')
    ? Date.parse(`${event.date}T${event.time}:00+07:00`)
: NaN
  if (scheduled > now) return vietnamese ? 'Chưa công bố' : 'Not released yet'
  return vietnamese ? 'Chưa có số liệu' : 'Unavailable'
}
