import { writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import {
  evaluateObject,
  extractObjectRange,
  isTranslatableText,
  loadCoreLocale,
  localeTargets,
  overrideModulePaths,
  placeholdersMatch,
  renderLocaleObject
} from './i18n-utils.mjs'

const root = resolve(process.cwd())
const langDir = join(root, 'src', 'locales', 'lang')
const outputPath = join(root, 'src', 'locales', 'generated-locale-overrides.js')
const authEndpoint = process.env.QUANTDINGER_TRANSLATE_AUTH_ENDPOINT ||
  'https://edge.microsoft.com/translate/auth'
const endpoint = process.env.QUANTDINGER_TRANSLATE_ENDPOINT ||
  'https://api-edge.cognitive.microsofttranslator.com/translate'
const requestDelayMs = Number(process.env.QUANTDINGER_TRANSLATE_DELAY_MS || 180)
const batchCharacterLimit = 3500
const batchItemLimit = 90

const sleep = milliseconds => new Promise(resolvePromise => setTimeout(resolvePromise, milliseconds))
let translationToken = ''

function protectText(value) {
  const protectedValues = []
  const text = value.replace(
    /<code\b[^>]*>.*?<\/code>|\{[^{}\n]+\}|%\([^)]+\)[sdif](?![A-Za-z])|%[sdif](?![A-Za-z])|<[^>\n]+>|`[^`\n]+`|https?:\/\/[A-Za-z0-9][A-Za-z0-9./?&=_:%#@+~-]*[A-Za-z0-9/#]/gi,
    match => {
      const token = `QDINGERPLACEHOLDER${String(protectedValues.length).padStart(6, '0')}TOKEN`
      protectedValues.push(match)
      return token
    }
  )
  return { text, protectedValues }
}

function restoreText(value, protectedValues) {
  let restored = value
  protectedValues.forEach((original, index) => {
    const token = `QDINGERPLACEHOLDER${String(index).padStart(6, '0')}TOKEN`
    if (!restored.includes(token)) {
      throw new Error(`Translation response lost protected token ${token}`)
    }
    restored = restored.split(token).join(original)
  })
  return restored.trim()
}

async function getTranslationToken(forceRefresh = false) {
  if (translationToken && !forceRefresh) return translationToken
  const response = await fetch(authEndpoint)
  if (!response.ok) throw new Error(`Translation auth failed with HTTP ${response.status}`)
  translationToken = (await response.text()).trim()
  if (!translationToken) throw new Error('Translation auth returned an empty token')
  return translationToken
}

async function requestTranslationMatrix(values, targetLanguages, attempt = 1) {
  const protectedItems = values.map(protectText)
  const query = new URLSearchParams({
    'api-version': '3.0',
    from: 'en',
    textType: 'plain'
  })
  targetLanguages.forEach(targetLanguage => query.append('to', targetLanguage))
  try {
    const token = await getTranslationToken()
    const response = await fetch(`${endpoint}?${query}`, {
      method: 'POST',
      headers: {
        authorization: `Bearer ${token}`,
        'content-type': 'application/json;charset=UTF-8'
      },
      body: JSON.stringify(protectedItems.map(item => ({ Text: item.text })))
    })
    if (!response.ok) {
      const error = new Error(`HTTP ${response.status}`)
      error.status = response.status
      throw error
    }
    const payload = await response.json()
    if (!Array.isArray(payload) || payload.length !== values.length) {
      throw new Error('Translation response item count mismatch')
    }
    return payload.map((item, index) => {
      const translations = {}
      for (const translated of item.translations || []) {
        try {
          translations[translated.to] = restoreText(
            translated.text || '',
            protectedItems[index].protectedValues
          )
        } catch (error) {
          console.warn(
            `Preserving source for ${translated.to} item ${index}: ${error.message}`
          )
          translations[translated.to] = values[index]
        }
      }
      return translations
    })
  } catch (error) {
    if (attempt >= 8) throw error
    if (error.status === 401 || error.status === 403) {
      await getTranslationToken(true)
    }
    const baseDelay = error.status === 429 ? 5000 : 1000
    await sleep(Math.min(baseDelay * (2 ** (attempt - 1)), 60000))
    return requestTranslationMatrix(values, targetLanguages, attempt + 1)
  }
}

function makeBatches(entries) {
  const batches = []
  let current = []
  let characters = 0
  for (const entry of entries) {
    const size = entry.source.length + 20
    if (current.length && (
      current.length >= batchItemLimit ||
      characters + size > batchCharacterLimit
    )) {
      batches.push(current)
      current = []
      characters = 0
    }
    current.push(entry)
    characters += size
  }
  if (current.length) batches.push(current)
  return batches
}

async function translateCandidateMatrix(candidateEntries, verifiedSame, phaseName) {
  const sourceByKey = new Map()
  const candidateKeys = {}
  const translatedByLocale = {}

  for (const [localeName, entries] of Object.entries(candidateEntries)) {
    candidateKeys[localeName] = new Set(entries.map(entry => entry.key))
    translatedByLocale[localeName] = {}
    entries.forEach(entry => sourceByKey.set(entry.key, entry.source))
  }

  const unionEntries = [...sourceByKey].map(([key, source]) => ({ key, source }))
  const batches = makeBatches(unionEntries)
  let completed = 0
  for (const batch of batches) {
    const activeLocales = Object.keys(localeTargets).filter(localeName => (
      batch.some(entry => candidateKeys[localeName].has(entry.key))
    ))
    const targetLanguages = activeLocales.map(localeName => localeTargets[localeName])
    const matrix = await requestTranslationMatrix(
      batch.map(entry => entry.source),
      targetLanguages
    )
    batch.forEach((entry, index) => {
      for (const localeName of activeLocales) {
        if (!candidateKeys[localeName].has(entry.key)) continue
        const targetLanguage = localeTargets[localeName]
        const value = matrix[index][targetLanguage]
        if (typeof value !== 'string') {
          throw new Error(`${localeName}:${entry.key} missing from translation response`)
        }
        if (!placeholdersMatch(entry.source, value)) {
          throw new Error(`${localeName}:${entry.key} changed interpolation placeholders`)
        }
        translatedByLocale[localeName][entry.key] = value
        if (value === entry.source) verifiedSame[localeName].add(entry.key)
      }
    })
    completed += batch.length
    console.log(`${phaseName}: translated ${completed}/${unionEntries.length} unique strings`)
    await sleep(requestDelayMs)
  }
  return translatedByLocale
}

function replaceLocaleObject(source, locale, fileName) {
  const range = extractObjectRange(source, 'const locale =', fileName)
  const objectSource = `{\n${renderLocaleObject(locale)}\n}`
  return `${source.slice(0, range.start)}${objectSource}${source.slice(range.end)}`
}

async function loadOverrideModules() {
  return Promise.all(
    overrideModulePaths.map(modulePath => import(new URL(modulePath, import.meta.url)))
  )
}

function composeOverrides(modules, localeName) {
  return Object.assign({}, ...modules.map(module => module.default?.[localeName] || {}))
}

function renderGeneratedOverrides(messages, verifiedSame) {
  const renderedMessages = Object.entries(messages)
    .map(([localeName, locale]) => {
      const body = renderLocaleObject(locale)
        .split('\n')
        .map(line => `    ${line.trimStart()}`)
        .join('\n')
      return `  ${JSON.stringify(localeName)}: {\n${body}\n  }`
    })
    .join(',\n')

  const renderedVerified = Object.entries(verifiedSame)
    .map(([localeName, keys]) => (
      `  ${JSON.stringify(localeName)}: ${JSON.stringify([...keys].sort())}`
    ))
    .join(',\n')

  return `// Generated by scripts/translate-incomplete-locales.mjs.\n` +
    `// Machine-generated strings are reviewed by placeholder and completeness audits.\n` +
    `const messages = {\n${renderedMessages}\n}\n\n` +
    `export const verifiedSameTranslations = {\n${renderedVerified}\n}\n\n` +
    `export default messages\n`
}

const coreLocales = {}
const verifiedSame = Object.fromEntries(
  Object.keys(localeTargets).map(localeName => [localeName, new Set()])
)
const enCore = loadCoreLocale(langDir, 'en-US').locale
coreLocales['en-US'] = enCore
const coreWork = {}
const coreCandidates = {}

for (const localeName of Object.keys(localeTargets)) {
  const filePath = join(langDir, `${localeName}.js`)
  const loaded = loadCoreLocale(langDir, localeName)
  const locale = { ...loaded.locale }
  const entries = Object.entries(enCore)
    .filter(([key, source]) => (
      isTranslatableText(source) &&
      (
        typeof locale[key] !== 'string' ||
        locale[key] === source ||
        !placeholdersMatch(source, locale[key])
      )
    ))
    .map(([key, source]) => ({ key, source }))

  console.log(`${localeName}: ${entries.length} core strings need translation`)
  coreCandidates[localeName] = entries
  coreWork[localeName] = { filePath, loaded, locale }
}

const coreTranslations = await translateCandidateMatrix(
  coreCandidates,
  verifiedSame,
  'core locales'
)

for (const localeName of Object.keys(localeTargets)) {
  const { filePath, loaded, locale } = coreWork[localeName]
  Object.assign(locale, coreTranslations[localeName])
  for (const [key, source] of Object.entries(enCore)) {
    if (locale[key] === undefined) locale[key] = source
  }

  const localeOnly = evaluateObject(loaded.source, 'const locale =', `${localeName}.js`)
  const mergedLocaleOnly = { ...localeOnly, ...locale }
  writeFileSync(
    filePath,
    replaceLocaleObject(loaded.source, mergedLocaleOnly, `${localeName}.js`),
    'utf8'
  )
  coreLocales[localeName] = locale
}

const overrideModules = await loadOverrideModules()
translationToken = ''
const enOverrides = composeOverrides(overrideModules, 'en-US')
const finalEnglish = { ...enCore, ...enOverrides }
const generatedMessages = {}
const generatedSeeds = {}
const overrideCandidates = {}

for (const localeName of Object.keys(localeTargets)) {
  const existingOverrides = composeOverrides(overrideModules, localeName)
  const current = { ...coreLocales[localeName], ...existingOverrides }
  const generated = {}
  const entries = []

  for (const [key, source] of Object.entries(finalEnglish)) {
    const target = current[key]
    if (typeof source !== 'string') {
      if (target === undefined) generated[key] = source
      continue
    }
    if (typeof target !== 'string') {
      if (isTranslatableText(source)) {
        entries.push({ key, source })
      } else {
        generated[key] = source
      }
    } else if (!placeholdersMatch(source, target)) {
      if (isTranslatableText(source)) {
        entries.push({ key, source })
      } else {
        generated[key] = source
      }
    } else if (target === source && isTranslatableText(source)) {
      entries.push({ key, source })
    }
  }

  console.log(`${localeName}: ${entries.length} effective override strings need translation`)
  generatedSeeds[localeName] = generated
  overrideCandidates[localeName] = entries
}

const overrideTranslations = await translateCandidateMatrix(
  overrideCandidates,
  verifiedSame,
  'effective overrides'
)

for (const localeName of Object.keys(localeTargets)) {
  generatedMessages[localeName] = {
    ...generatedSeeds[localeName],
    ...overrideTranslations[localeName]
  }
}

writeFileSync(outputPath, renderGeneratedOverrides(generatedMessages, verifiedSame), 'utf8')
console.log(`Wrote complete locale overrides to ${outputPath}`)
