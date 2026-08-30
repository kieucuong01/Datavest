import { getMarketModules } from '@/api/marketModules'
import { ACTIVE_MARKET_ORDER, isActiveMarket, normalizeSupportedMarket } from '@/utils/supportedMarkets'

export const FALLBACK_MARKET_MODULES = [
  { key: 'VNStock', label: 'Vietnam Stocks', enabled: true, features: ['research', 'backtest', 'paper'] },
  { key: 'Crypto', label: 'Crypto', enabled: true, features: ['research', 'backtest', 'paper'] },
  { key: 'Forex', label: 'Gold (XAU)', enabled: true, features: ['research', 'backtest', 'paper'] }
]

export function toMarketOption (module) {
  const key = normalizeSupportedMarket(module && (module.key || module.value))
  return {
    value: key,
    label: module.label || key,
    i18nKey: `dashboard.analysis.market.${key}`,
    module
  }
}

export async function loadEnabledMarketOptions (opts = {}) {
  const include = Array.isArray(opts.includeFeatures) ? opts.includeFeatures : []
  const fallback = Array.isArray(opts.fallback) ? opts.fallback : FALLBACK_MARKET_MODULES
  try {
    const res = await getMarketModules()
    const markets = res && res.code === 1 && res.data && Array.isArray(res.data.markets)
      ? res.data.markets
      : fallback
    return markets
      .map(market => {
        try {
          const key = normalizeSupportedMarket(market && (market.key || market.value))
          return { ...market, key }
        } catch (error) {
          return null
        }
      })
      .filter(Boolean)
      .sort((left, right) => ACTIVE_MARKET_ORDER.indexOf(left.key) - ACTIVE_MARKET_ORDER.indexOf(right.key))
      .filter(market => isActiveMarket(market.key))
      .filter(market => market && market.enabled !== false)
      .filter(market => {
        if (include.length === 0) return true
        const features = market.features || []
        return include.some(feature => features.includes(feature))
      })
      .map(toMarketOption)
  } catch (e) {
    return fallback
      .filter(market => {
        try {
          normalizeSupportedMarket(market && (market.key || market.value))
          return true
        } catch (error) {
          return false
        }
      })
      .sort((left, right) => ACTIVE_MARKET_ORDER.indexOf(left.key) - ACTIVE_MARKET_ORDER.indexOf(right.key))
      .filter(market => isActiveMarket(market.key))
      .filter(market => market && market.enabled !== false)
      .map(toMarketOption)
  }
}

export function firstMarketValue (options, fallback = 'Crypto') {
  return options && options.length > 0 ? options[0].value : normalizeSupportedMarket(fallback)
}
