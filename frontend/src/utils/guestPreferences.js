import { hasAccessToken } from './guestAccess.js'

export const GUEST_DEFAULT_THEME = 'light'
export const GUEST_DEFAULT_LANGUAGE = 'vi-VN'

const validThemes = new Set(['light', 'dark', 'realdark'])
const supportedLanguages = new Set(['en-US', 'vi-VN'])

export function resolveInitialPreferences ({
  token,
  savedTheme,
  savedLanguage,
  theme = 'realdark',
  language = 'en-US'
} = {}) {
  const isGuest = !hasAccessToken(token)

  return {
    theme: validThemes.has(savedTheme)
      ? savedTheme
      : (isGuest ? GUEST_DEFAULT_THEME : theme),
    language: supportedLanguages.has(savedLanguage)
      ? savedLanguage
      : (isGuest ? GUEST_DEFAULT_LANGUAGE : language)
  }
}
