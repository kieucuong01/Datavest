export function normalizeAccessToken (rawToken) {
  let value = rawToken
  if (value && typeof value === 'object') {
    value = value.token || value.value
  }

  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function hasAccessToken (rawToken) {
  return Boolean(normalizeAccessToken(rawToken))
}

export function loginTarget (fullPath) {
  const redirect = String(fullPath || '').trim()
  return redirect
    ? { path: '/user/login', query: { redirect } }
    : { path: '/user/login' }
}

export function resolvePostLoginPath (rawRedirect) {
  const redirect = String(rawRedirect || '').trim()
  if (!redirect.startsWith('/') || redirect.startsWith('//')) {
    return '/smart-insights'
  }
  return redirect
}
