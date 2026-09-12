import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildGuestRoutes,
  isPublicPath,
  requiresAuthentication
} from '../../src/router/access.js'


function findRoute (routes, path) {
  for (const route of routes) {
    if (route.path === path) return route
    const child = findRoute(route.children || [], path)
    if (child) return child
  }
  return null
}


const fixtureRoutes = [
  {
    path: '/',
    meta: { access: 'public' },
    children: [
      { path: '/smart-insights', meta: { access: 'public', icon: 'bulb' } },
      { path: '/indicator-ide', meta: { access: 'public', icon: 'line-chart' } },
      { path: '/ai-asset-analysis', meta: { access: 'authenticated', icon: 'robot' } },
      { path: '/strategy-ide', meta: { access: 'authenticated', icon: 'code' } },
      { path: '/settings', meta: { access: 'authenticated', permission: ['admin'], icon: 'setting' } }
    ]
  }
]


test('guest routes retain public pages, lock private pages, and remove admin pages', () => {
  const routes = buildGuestRoutes(fixtureRoutes)

  assert.equal(findRoute(routes, '/smart-insights').meta.guestLocked, false)
  assert.equal(findRoute(routes, '/indicator-ide').meta.guestLocked, false)
  assert.equal(findRoute(routes, '/ai-asset-analysis').meta.guestLocked, true)
  assert.equal(findRoute(routes, '/ai-asset-analysis').meta.featureIcon, 'robot')
  assert.equal(findRoute(routes, '/strategy-ide').meta.icon, 'lock')
  assert.equal(findRoute(routes, '/settings'), null)
  assert.equal(fixtureRoutes[0].children[2].meta.icon, 'robot')
})


test('public path matching is exact and ignores query strings', () => {
  assert.equal(isPublicPath('/'), true)
  assert.equal(isPublicPath('/smart-insights'), true)
  assert.equal(isPublicPath('/smart-insights?as_of=2026-09-12'), true)
  assert.equal(isPublicPath('/indicator-ide'), true)
  assert.equal(isPublicPath('/strategy-ide'), false)
  assert.equal(isPublicPath('/portfolio'), false)
  assert.equal(isPublicPath('/smart-insights/private'), false)
})


test('route access metadata is the authorization decision for registered routes', () => {
  assert.equal(requiresAuthentication({ meta: { access: 'public' } }), false)
  assert.equal(requiresAuthentication({ meta: { access: 'authenticated' } }), true)
  assert.equal(requiresAuthentication({ meta: {} }), true)
  assert.equal(requiresAuthentication(null), true)
})
