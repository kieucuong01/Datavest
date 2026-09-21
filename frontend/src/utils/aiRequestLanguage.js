const PRODUCT_LANGUAGES = {
  en: 'en-US',
  'en-us': 'en-US',
  vi: 'vi-VN',
  'vi-vn': 'vi-VN'
}

function normalizeProductLanguage (language) {
  if (!language) return ''
  return PRODUCT_LANGUAGES[String(language).trim().replace('_', '-').toLowerCase()] || ''
}

// Vuex is the source of truth for the language selected in Settings. i18n is
// retained only as a safe fallback while an application page is mounting.
export function resolveAiRequestLanguage (settingsLanguage, i18nLanguage) {
  return normalizeProductLanguage(settingsLanguage) || normalizeProductLanguage(i18nLanguage) || 'en-US'
}
