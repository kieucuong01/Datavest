import { hasAccessToken } from './guestAccess.js'

export const GUEST_DEFAULT_THEME = 'light'
export const GUEST_DEFAULT_LANGUAGE = 'vi-VN'
export const GUEST_PREFERENCE_VERSION = '1'
export const GUEST_PREFERENCE_VERSION_STORAGE_KEY = 'guest_preferences_version'

const validThemes = new Set(['light', 'dark', 'realdark'])
const supportedLanguages = new Set(['en-US', 'vi-VN'])

export function resolveInitialPreferences ({
  token,
  savedTheme,
  savedLanguage,
  guestPreferenceVersion,
  theme = 'realdark',
  language = 'en-US'
} = {}) {
  const isGuest = !hasAccessToken(token)
  const hasCurrentGuestPreferences = guestPreferenceVersion === GUEST_PREFERENCE_VERSION

  if (isGuest && !hasCurrentGuestPreferences) {
    return {
      theme: GUEST_DEFAULT_THEME,
      language: GUEST_DEFAULT_LANGUAGE
    }
  }

  return {
    theme: validThemes.has(savedTheme)
      ? savedTheme
      : (isGuest ? GUEST_DEFAULT_THEME : theme),
    language: supportedLanguages.has(savedLanguage)
      ? savedLanguage
      : (isGuest ? GUEST_DEFAULT_LANGUAGE : language)
  }
}
