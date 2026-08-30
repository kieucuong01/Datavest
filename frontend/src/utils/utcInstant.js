/**
 * Parse API/backtest timestamps as absolute instants.
 *
 * Historical backtest payloads used UTC wall-clock strings without a timezone
 * suffix. Browsers otherwise interpret those strings in their local timezone,
 * shifting chart markers away from the actual candle.
 */
export function parseUtcAwareInstant (input) {
  if (input == null || input === '') return null
  if (input instanceof Date) return Number.isNaN(input.getTime()) ? null : input

  if (typeof input === 'number') {
    const date = new Date(input < 1e12 ? input * 1000 : input)
    return Number.isNaN(date.getTime()) ? null : date
  }

  if (typeof input === 'string') {
    const value = input.trim()
    if (!value) return null
    if (/^\d+$/.test(value)) return parseUtcAwareInstant(Number(value))

    const isNaive = /^\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}(:\d{2})?(\.\d+)?$/.test(value) &&
      !/[zZ]|[+-]\d{2}:?\d{2}$/.test(value)
    let normalized = value
    if (isNaive) {
      normalized = value.replace(/\//g, '-').replace(' ', 'T')
      if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(normalized)) normalized += ':00'
      normalized += 'Z'
    }
    const date = new Date(normalized)
    return Number.isNaN(date.getTime()) ? null : date
  }

  return null
}

export function timestampMillisecondsUtc (input) {
  const date = parseUtcAwareInstant(input)
  return date ? date.getTime() : null
}
