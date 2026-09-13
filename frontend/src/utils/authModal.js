import Vue from 'vue'

export const authModalBus = new Vue()

let authModalReady = false

export function setAuthModalReady (ready) {
  authModalReady = Boolean(ready)
}

export function isAuthModalReady () {
  return authModalReady
}

export function openAuthModal (options = {}) {
  if (!authModalReady) return false
  authModalBus.$emit('open', options)
  return true
}

export function closeAuthModal () {
  authModalBus.$emit('close')
}
