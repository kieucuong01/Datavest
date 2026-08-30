import store from '@/store'
import storage from 'store'
import {
  ACCESS_TOKEN,
  APP_LANGUAGE,
  TOGGLE_CONTENT_WIDTH,
  TOGGLE_FIXED_HEADER,
  TOGGLE_FIXED_SIDEBAR, TOGGLE_HIDE_HEADER,
  TOGGLE_LAYOUT, TOGGLE_NAV_THEME, TOGGLE_WEAK,
  TOGGLE_COLOR, TOGGLE_MULTI_TAB
} from '@/store/mutation-types'
import { printANSI } from '@/utils/screenLog'
import defaultSettings from '@/config/defaultSettings'
import { defaultLang, supportedLocales } from '@/locales'

export default function Initializer () {
  printANSI() // 请自行移除该行.  please remove this line

  const legacyDefaultColor = '#13C2C2'
  const savedLayout = storage.get(TOGGLE_LAYOUT, defaultSettings.layout)
  const nextLayout = defaultSettings.layout === 'topmenu' && savedLayout === 'sidemenu'
    ? defaultSettings.layout
    : savedLayout
  const savedTheme = storage.get(TOGGLE_NAV_THEME)
  const savedColor = storage.get(TOGGLE_COLOR)
  const validThemes = ['light', 'dark', 'realdark']
  const nextTheme = validThemes.includes(savedTheme) ? savedTheme : defaultSettings.navTheme
  const nextColor = !savedColor || String(savedColor).toUpperCase() === legacyDefaultColor ? defaultSettings.primaryColor : savedColor
  store.commit(TOGGLE_LAYOUT, nextLayout)
  store.commit(TOGGLE_FIXED_HEADER, storage.get(TOGGLE_FIXED_HEADER, defaultSettings.fixedHeader))
  store.commit(TOGGLE_FIXED_SIDEBAR, storage.get(TOGGLE_FIXED_SIDEBAR, defaultSettings.fixSiderbar))
  const savedContentWidth = storage.get(TOGGLE_CONTENT_WIDTH, defaultSettings.contentWidth)
  store.commit(TOGGLE_CONTENT_WIDTH, nextLayout === 'topmenu' ? defaultSettings.contentWidth : savedContentWidth)
  store.commit(TOGGLE_HIDE_HEADER, storage.get(TOGGLE_HIDE_HEADER, defaultSettings.autoHideHeader))
  store.commit(TOGGLE_NAV_THEME, nextTheme)
  store.commit(TOGGLE_WEAK, storage.get(TOGGLE_WEAK, defaultSettings.colorWeak))
  store.commit(TOGGLE_COLOR, nextColor)
  store.commit(TOGGLE_MULTI_TAB, storage.get(TOGGLE_MULTI_TAB, defaultSettings.multiTab))
  let token = storage.get(ACCESS_TOKEN)
  if (token && typeof token !== 'string') {
    token = token.token || token.value || (typeof token === 'object' ? null : token)
  }
  token = typeof token === 'string' ? token : null
  store.commit('SET_TOKEN', token)

  const savedLanguage = storage.get(APP_LANGUAGE, defaultLang)
  const nextLanguage = supportedLocales.includes(savedLanguage) ? savedLanguage : defaultLang
  store.dispatch('setLang', nextLanguage)

  // Fire-and-forget: pull brand / legal / contact config from backend so the
  // sidebar footer, login page, version label and legal modals reflect the
  // current deployment.  Errors are swallowed inside the action and we fall
  // back to the cached / default brand values, so this can never block boot.
  store.dispatch('LoadBrandConfig').catch(() => {})

  // last step
}
