import request from '@/utils/request'

export function getFactorCatalog (params = {}) {
  return request({ url: '/api/factors', method: 'get', params })
}

export function getFactorDetail (factorId) {
  return request({ url: `/api/factors/${factorId}`, method: 'get' })
}

export function runFactorResearch (data) {
  return request({ url: '/api/factors/research', method: 'post', data })
}
