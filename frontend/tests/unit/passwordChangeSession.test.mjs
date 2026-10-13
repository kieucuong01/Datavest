import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

for (const mode of ['local', 'remote', 'remote failure']) {
  test(`${mode} logout clears cached and reactive user state`, async () => {
    const removed = []
    const committed = {}
    const dispatched = []
    let requests = 0
    const source = readFileSync(new URL('../../src/store/modules/user.js', import.meta.url), 'utf8')
      .replace(/^import[^\n]+\n/gm, '')
      .replace('const user =', 'globalThis.user =')
      .replace('export default user', '')
    const context = {
      storage: { addPlugin () {}, get () {}, remove: key => removed.push(key) },
      expirePlugin: {}, ACCESS_TOKEN: 'token', USER_INFO: 'info', USER_ROLES: 'roles',
      welcome: () => '', logout: async () => {
        requests++
        if (mode === 'remote failure') throw new Error('expired session')
      }
    }
    vm.runInNewContext(source, context)
    await context.user.actions.Logout({
      commit: (key, value) => { committed[key] = value },
      dispatch: action => { dispatched.push(action) }
    }, { localOnly: mode === 'local' })

    assert.equal(requests, mode === 'local' ? 0 : 1)
    assert.equal(committed.SET_TOKEN, '')
    assert.equal(committed.SET_NAME.name, '')
    assert.equal(committed.SET_AVATAR, '')
    assert.equal(committed.SET_ROLES.length, 0)
    assert.equal(Object.keys(committed.SET_INFO).length, 0)
    assert.deepEqual(removed.sort(), ['info', 'roles', 'token'])
    assert.deepEqual(dispatched, ['ResetRoutes'])
  })
}

for (const successful of [true, false]) {
  test(`password change ${successful ? 'success returns to login' : 'failure preserves session'}`, async () => {
    const source = readFileSync(new URL('../../src/views/profile/index.vue', import.meta.url), 'utf8')
    const start = source.indexOf('    handleChangePassword () {')
    const end = source.indexOf('    async loadMfaStatus', start)
    const method = source.slice(start, end).trim().replace(/,$/, '')
      .replace("await import('@/api/auth')", '{ changePassword: apiChangePassword }')
    const calls = []
    let completion
    const component = vm.runInNewContext(`({ ${method} })`, {
      apiChangePassword: async () => ({ code: successful ? 1 : 0 })
    })
    const page = {
      passwordForm: {
        validateFields: callback => { completion = callback(null, { code: '123456', new_password: 'NewPassword1' }) },
        resetFields () {}
      },
      $message: { success () {}, error () {} },
      $store: { dispatch: async (action, options) => { calls.push([action, options?.localOnly]) } },
      $router: { replace: route => { calls.push(['route', route.path]) } }
    }
    component.handleChangePassword.call(page)
    await completion
    assert.deepEqual(calls, successful ? [['Logout', true], ['route', '/user/login']] : [])
    assert.equal(page.changingPassword, false)
  })
}
