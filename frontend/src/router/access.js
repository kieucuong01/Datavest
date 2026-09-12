export const ROUTE_ACCESS = Object.freeze({
  PUBLIC: 'public',
  AUTHENTICATED: 'authenticated'
})

const PUBLIC_PATHS = new Set(['/', '/smart-insights', '/indicator-ide', '/user/login', '/404'])

function pathOnly (value) {
  return String(value || '').split('#', 1)[0].split('?', 1)[0] || '/'
}

export function isPublicPath (value) {
  return PUBLIC_PATHS.has(pathOnly(value))
}

export function requiresAuthentication (route) {
  return !route || !route.meta || route.meta.access !== ROUTE_ACCESS.PUBLIC
}

function requiresAdmin (route) {
  const permissions = route && route.meta && Array.isArray(route.meta.permission)
    ? route.meta.permission
    : []
  return permissions.includes('admin')
}

export function buildGuestRoutes (routes = []) {
  return routes
    .filter(route => !requiresAdmin(route))
    .map(route => {
      const cloned = { ...route }
      const isPublic = !requiresAuthentication(route)
      cloned.meta = {
        ...(route.meta || {}),
        guestLocked: !isPublic
      }
      if (!isPublic) {
        cloned.meta.featureIcon = cloned.meta.icon || ''
        cloned.meta.icon = 'lock'
      }
      if (Array.isArray(route.children)) {
        cloned.children = buildGuestRoutes(route.children)
      }
      return cloned
    })
}
