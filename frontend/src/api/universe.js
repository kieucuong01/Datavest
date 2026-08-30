import request from '@/utils/request'

export function getUniverses () {
  return request({ url: '/api/universes', method: 'get' })
}

export function createUniverse (data) {
  return request({ url: '/api/universes', method: 'post', data })
}

export function getUniverseMembers (universeId, params = {}) {
  return request({ url: `/api/universes/${universeId}/members`, method: 'get', params })
}

export function replaceUniverseMembers (universeId, members) {
  return request({ url: `/api/universes/${universeId}/members`, method: 'put', data: { members } })
}

export function createUniverseSnapshot (universeId, data = {}) {
  return request({ url: `/api/universes/${universeId}/snapshots`, method: 'post', data })
}

export function cloneUniverse (universeId, data = {}) {
  return request({ url: `/api/universes/${universeId}/clone`, method: 'post', data })
}

export function getSystemUniverseOverview () {
  return request({ url: '/api/universes/admin/overview', method: 'get' })
}

export function syncSystemUniverses (data = {}) {
  return request({ url: '/api/universes/admin/sync', method: 'post', data })
}
