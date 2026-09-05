import Vue from 'vue'
import VueI18n from 'vue-i18n'
import storage from 'store'
import moment from 'moment'
import enUS from './lang/en-US'
import copilotOverrides from './copilot-overrides'
import profileSecurityMessages from './lang/profile-security'
import brokerAccountWorkspaceMessages from './lang/broker-account-workspace'
import strategyV2Messages from './lang/strategy-v2'
import strategyLiveRiskMessages from './lang/strategy-live-risk'
import robotBuilderMessages from './lang/robot-builder-overrides'
import strategyTradeRecordMessages from './lang/strategy-trade-records'
import generatedLocaleOverrides from './generated-locale-overrides'
import portfolioOptimizerMessages from './portfolio-optimizer'
import smartInsightsMessages from './smart-insights'
import tradingAgentsMessages from './trading-agents'
import productLocaleOverrides from './product-locale-overrides'

Vue.use(VueI18n)

export const defaultLang = 'en-US'
// DataVest currently exposes only the two product languages. Keep the other
// dictionaries available for compatibility, but never select them at runtime.
export const supportedLocales = Object.freeze([defaultLang, 'vi-VN'])

const messages = {
  [defaultLang]: {
    ...enUS,
    ...(copilotOverrides[defaultLang] || {}),
    ...(profileSecurityMessages[defaultLang] || {}),
    ...(brokerAccountWorkspaceMessages[defaultLang] || {}),
    ...(strategyV2Messages[defaultLang] || {}),
    ...(strategyLiveRiskMessages[defaultLang] || {}),
    ...(robotBuilderMessages[defaultLang] || {}),
    ...(strategyTradeRecordMessages[defaultLang] || {}),
    ...(portfolioOptimizerMessages[defaultLang] || {}),
    ...(smartInsightsMessages[defaultLang] || {}),
    ...(tradingAgentsMessages[defaultLang] || {}),
    ...(productLocaleOverrides[defaultLang] || {}),
    ...(generatedLocaleOverrides[defaultLang] || {})
  }
}

const localeLoaders = {
  'vi-VN': () => import('./lang/vi-VN.js')
}

const i18n = new VueI18n({
  silentTranslationWarn: true,
  silentFallbackWarn: true,
  locale: defaultLang,
  fallbackLocale: defaultLang,
  messages
})

const loadedLanguages = [defaultLang]

function sanitizeLocaleMessage (message) {
  if (Array.isArray(message)) {
    return message
      .map(item => sanitizeLocaleMessage(item))
      .filter(item => item !== undefined)
  }

  if (message && typeof message === 'object') {
    return Object.keys(message).reduce((result, key) => {
      const value = sanitizeLocaleMessage(message[key])
      if (value !== undefined) {
        result[key] = value
      }
      return result
    }, {})
  }

  if (typeof message === 'string') {
    return message.includes('\uFFFD') ? undefined : message
  }

  return message
}

function setI18nLanguage (lang) {
  i18n.locale = lang
  const html = document.documentElement
  const isRtl = /^ar/i.test(lang)
  if (html) {
    html.setAttribute('lang', lang)
    html.setAttribute('dir', isRtl ? 'rtl' : 'ltr')
  }
  if (document.body) {
    document.body.setAttribute('dir', isRtl ? 'rtl' : 'ltr')
    document.body.classList.toggle('rtl', isRtl)
  }
  return lang
}

function mergeLocaleOverrides (lang) {
  const overrides = {
    ...(copilotOverrides[lang] || {}),
    ...(profileSecurityMessages[lang] || {}),
    ...(brokerAccountWorkspaceMessages[lang] || {}),
    ...(strategyV2Messages[lang] || {}),
    ...(strategyLiveRiskMessages[lang] || {}),
    ...(robotBuilderMessages[lang] || {}),
    ...(strategyTradeRecordMessages[lang] || {}),
    ...(portfolioOptimizerMessages[lang] || {}),
    ...(smartInsightsMessages[lang] || {}),
    ...(tradingAgentsMessages[lang] || {}),
    ...(productLocaleOverrides[lang] || {}),
    ...(generatedLocaleOverrides[lang] || {})
  }
  i18n.setLocaleMessage(lang, {
    ...(i18n.getLocaleMessage(lang) || {}),
    ...overrides
  })
}

export async function loadLanguageAsync (lang = defaultLang) {
  const nextLang = supportedLocales.includes(lang) ? lang : defaultLang
  storage.set('lang', nextLang)
  if (i18n.locale === nextLang) {
    mergeLocaleOverrides(nextLang)
    return setI18nLanguage(nextLang)
  }

  if (!loadedLanguages.includes(nextLang)) {
    const loadLocale = localeLoaders[nextLang]
    if (!loadLocale) return setI18nLanguage(defaultLang)

    const msg = await loadLocale()
    const locale = sanitizeLocaleMessage({
      ...msg.default,
      ...(copilotOverrides[nextLang] || {}),
      ...(profileSecurityMessages[nextLang] || {}),
      ...(brokerAccountWorkspaceMessages[nextLang] || {}),
      ...(strategyLiveRiskMessages[nextLang] || {}),
      ...(robotBuilderMessages[nextLang] || {}),
      ...(strategyTradeRecordMessages[nextLang] || {}),
      ...(portfolioOptimizerMessages[nextLang] || {}),
      ...(smartInsightsMessages[nextLang] || {}),
      ...(tradingAgentsMessages[nextLang] || {}),
      ...(productLocaleOverrides[nextLang] || {}),
      ...(generatedLocaleOverrides[nextLang] || {})
    })
    i18n.setLocaleMessage(nextLang, locale)
    loadedLanguages.push(nextLang)
    if (locale.momentName && locale.momentLocale) {
      moment.updateLocale(locale.momentName, locale.momentLocale)
    }
  }

  mergeLocaleOverrides(nextLang)
  return setI18nLanguage(nextLang)
}

export function i18nRender (key) {
  return i18n.t(`${key}`)
}

export default i18n
