/** Display names for crypto exchange_id values (shared across account pickers). */
export const CRYPTO_EXCHANGE_DISPLAY_NAMES = {
  binance: 'Binance',
  okx: 'OKX',
  bitget: 'Bitget',
  bybit: 'Bybit',
  gate: 'Gate.io',
  htx: 'HTX',
  alpaca: 'Alpaca',
  ibkr: 'IBKR'
}

export const CRYPTO_EXCHANGE_IDS = new Set([
  'binance',
  'okx',
  'bitget',
  'bybit',
  'gate',
  'htx'
])

export const QUICK_TRADE_EXCHANGE_IDS = new Set([
  'binance',
  'okx',
  'bitget',
  'bybit',
  'gate',
  'htx'
])

export function isCryptoExchangeCredential (cred) {
  return CRYPTO_EXCHANGE_IDS.has(String(cred?.exchange_id || '').trim().toLowerCase())
}

export function filterCryptoExchangeCredentials (credentials, exchangeId) {
  const selectedExchangeId = String(exchangeId || '').trim().toLowerCase()
  return (Array.isArray(credentials) ? credentials : []).filter(cred => {
    const credentialExchangeId = String(cred?.exchange_id || '').trim().toLowerCase()
    return CRYPTO_EXCHANGE_IDS.has(credentialExchangeId) &&
      (!selectedExchangeId || credentialExchangeId === selectedExchangeId)
  })
}

export function isQuickTradeExchangeCredential (cred) {
  return QUICK_TRADE_EXCHANGE_IDS.has(String(cred?.exchange_id || '').trim().toLowerCase())
}

export function getExchangeDisplayName (exchangeId) {
  const id = String(exchangeId || '').trim().toLowerCase()
  if (!id) return '--'
  return CRYPTO_EXCHANGE_DISPLAY_NAMES[id] || id.toUpperCase()
}

/**
 * Human-readable label for a saved exchange credential (select options, lists).
 * @param {object} cred - row from /api/credentials/list
 * @param {{ unnamed?: string, includeHint?: boolean }} opts
 */
export function formatExchangeCredentialLabel (cred, opts = {}) {
  if (!cred) return ''
  const { unnamed = '', includeHint = true } = opts
  const alias = String(cred.name || '').trim()
  const ex = getExchangeDisplayName(cred.exchange_id)
  const hint = includeHint && cred.api_key_hint ? String(cred.api_key_hint).trim() : ''
  if (alias) {
    return hint ? `${ex} · ${alias} (${hint})` : `${ex} · ${alias}`
  }
  if (hint) return `${ex} (${hint})`
  return unnamed ? `${ex} · ${unnamed}` : ex
}
