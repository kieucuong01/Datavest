import { join, resolve } from 'node:path'
import {
  isTranslatableText,
  loadCoreLocale,
  localeTargets,
  overrideModulePaths,
  placeholdersMatch
} from './i18n-utils.mjs'
import generatedOverrides, {
  verifiedSameTranslations
} from '../src/locales/generated-locale-overrides.js'

const root = resolve(process.cwd())
const langDir = join(root, 'src', 'locales', 'lang')
const overrideModules = await Promise.all(
  overrideModulePaths.map(modulePath => import(new URL(modulePath, import.meta.url)))
)

function composeOverrides(localeName) {
  return Object.assign(
    {},
    ...overrideModules.map(module => module.default?.[localeName] || {}),
    generatedOverrides[localeName] || {}
  )
}

function finalMessages(localeName) {
  return {
    ...loadCoreLocale(langDir, localeName).locale,
    ...composeOverrides(localeName)
  }
}

const english = finalMessages('en-US')
const failures = []
const coverage = []

for (const localeName of Object.keys(localeTargets)) {
  const locale = finalMessages(localeName)
  const verifiedSame = new Set(verifiedSameTranslations[localeName] || [])
  const missing = []
  const placeholderMismatches = []
  const untranslated = []

  for (const [key, source] of Object.entries(english)) {
    const target = locale[key]
    if (target === undefined || target === null) {
      missing.push(key)
      continue
    }
    if (typeof source !== 'string') {
      if (typeof target !== typeof source) missing.push(key)
      continue
    }
    if (typeof target !== 'string') {
      missing.push(key)
      continue
    }
    if (!placeholdersMatch(source, target)) {
      placeholderMismatches.push(key)
    }
    if (
      target === source &&
      isTranslatableText(source) &&
      !verifiedSame.has(key)
    ) {
      untranslated.push(key)
    }
  }

  coverage.push({
    locale: localeName,
    keys: Object.keys(locale).length,
    missing: missing.length,
    placeholderMismatches: placeholderMismatches.length,
    untranslated: untranslated.length
  })

  if (missing.length) {
    failures.push(`${localeName}: missing ${missing.length} keys (${missing.slice(0, 8).join(', ')})`)
  }
  if (placeholderMismatches.length) {
    failures.push(
      `${localeName}: ${placeholderMismatches.length} placeholder mismatches ` +
      `(${placeholderMismatches.slice(0, 8).join(', ')})`
    )
  }
  if (untranslated.length) {
    failures.push(
      `${localeName}: ${untranslated.length} unverified English fallbacks ` +
      `(${untranslated.slice(0, 8).join(', ')})`
    )
  }
}

console.table(coverage)

if (failures.length) {
  console.error('Locale completeness audit failed:')
  failures.forEach(failure => console.error(`- ${failure}`))
  process.exit(1)
}

console.log(`Locale completeness audit passed for ${Object.keys(localeTargets).length} translated locales.`)
