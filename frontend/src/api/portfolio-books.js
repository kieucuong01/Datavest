import request from '@/utils/request'
const base = '/api/portfolio/books'
export const listBooks = () => request({ url: base, method: 'get' })
export const createBook = data => request({ url: base, method: 'post', data })
export const bookState = id => request({ url: `${base}/${id}/state`, method: 'get' })
export const bookEntries = (id, params = {}) => request({ url: `${base}/${id}/entries`, method: 'get', params })
export const addEntries = (id, data) => request({ url: `${base}/${id}/entries`, method: 'post', data })
export const reviseEntry = (id, eventId, data) => request({ url: `${base}/${id}/entries/${eventId}/revisions`, method: 'post', data })
export const entryRevisions = (id, eventId) => request({ url: `${base}/${id}/entries/${eventId}/revisions`, method: 'get' })
export const importPreview = (id, data) => request({ url: `${base}/${id}/import/preview`, method: 'post', data })
export const importCommit = (id, data) => request({ url: `${base}/${id}/import/commit`, method: 'post', data })
export const openingPreview = (id, data) => request({ url: `${base}/${id}/opening/preview`, method: 'post', data })
export const openingCommit = (id, data) => request({ url: `${base}/${id}/opening/commit`, method: 'post', data })
