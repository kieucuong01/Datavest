import { parseUtcAwareInstant } from './utcInstant.js'

export const VIETNAM_TIME_ZONE = 'Asia/Ho_Chi_Minh'

function localeOrDefault (locale) {
  return locale || 'vi-VN'
}

function partsFor (input) {
  const date = parseUtcAwareInstant(input)
  if (!date) return null
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: VIETNAM_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23'
  }).formatToParts(date).reduce((result, part) => ({ ...result, [part.type]: part.value }), {})
}

function formatVietnamInstant (input, locale, options, fallback) {
  const date = parseUtcAwareInstant(input)
  if (!date) return fallback
  return date.toLocaleString(localeOrDefault(locale), { timeZone: VIETNAM_TIME_ZONE, ...options })
}

export function formatVietnamDateTime (input, { locale, fallback = '—' } = {}) {
  return formatVietnamInstant(input, locale, {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
  }, fallback)
}

export function formatVietnamDate (input, { locale, fallback = '—', short = false } = {}) {
  return formatVietnamInstant(input, locale, {
    year: short ? undefined : 'numeric', month: short ? 'short' : '2-digit', day: '2-digit'
  }, fallback)
}

export function formatVietnamTime (input, { locale, fallback = '—' } = {}) {
  return formatVietnamInstant(input, locale, { hour: '2-digit', minute: '2-digit', hour12: false }, fallback)
}

export function vietnamDateKey (input) {
  const parts = partsFor(input)
  return parts ? `${parts.year}-${parts.month}-${parts.day}` : ''
}

export function vietnamTimeKey (input) {
  const parts = partsFor(input)
  return parts ? `${parts.hour}:${parts.minute}` : ''
}
