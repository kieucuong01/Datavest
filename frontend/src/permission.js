import router, {
  resetRouter
} from './router'
import store from './store'
import storage from 'store'
import NProgress from 'nprogress' // progress bar
import '@/components/NProgress/nprogress.less' // progress bar custom style
import {
  setDocumentTitle,
  domTitle
} from '@/utils/domUtil'
import {
  ACCESS_TOKEN
} from '@/store/mutation-types'
import {
  i18nRender
} from '@/locales'
import { promptChangeInitialPassword } from '@/utils/initialPasswordReminder'
import { isPublicPath } from '@/router/access'
import { normalizeAccessToken, resolvePostLoginPath } from '@/utils/guestAccess'
import { isAuthModalReady, openAuthModal } from '@/utils/authModal'

NProgress.configure({
  showSpinner: false
}) // NProgress Configuration

const allowList = ['login'] // no redirect allowList
const loginRoutePath = '/user/login'
function installGeneratedRoutes (action, payload) {
  return store.dispatch(action, payload).then(() => {
    resetRouter()
    store.getters.addRouters.forEach(route => router.addRoute(route))
  })
}

router.beforeEach((to, from, next) => {
  NProgress.start() // start progress bar
  to.meta && typeof to.meta.title !== 'undefined' && setDocumentTitle(`${i18nRender(to.meta.title)} - ${domTitle}`)

  // Check whether we have a token (local-only auth).
  const token = normalizeAccessToken(storage.get(ACCESS_TOKEN))

  if (token) {
    if (to.path === loginRoutePath) {
      next({ path: resolvePostLoginPath(to.query.redirect) })
      NProgress.done()
    } else {
      if (store.getters.roles.length === 0) {
        store.dispatch('GetInfo')
          .then(res => {
            // const roles = res && res.role
            promptChangeInitialPassword()
            installGeneratedRoutes('GenerateRoutes', { token }).then(() => {
              next({ ...to, replace: true })
            })
          })
          .catch((err) => {
            // If token is invalid/expired, clear local auth and redirect to login.
            const status = err && err.response && err.response.status
            if (status === 401) {
              store.dispatch('Logout').finally(() => {
                if (isPublicPath(to.fullPath || to.path)) {
                  installGeneratedRoutes('GenerateGuestRoutes').then(() => next({ ...to, replace: true }))
                } else {
                  next({ path: loginRoutePath, query: { redirect: to.fullPath } })
                }
                NProgress.done()
              })
              return
            }

            // Do NOT hard-logout on transient failures (backend down, proxy issue, etc).
            // Instead, degrade gracefully with a default role and continue.
            store.commit('SET_ROLES', [{ id: 'default', permissionList: [] }])
            installGeneratedRoutes('GenerateRoutes', { token }).then(() => {
              next({ ...to, replace: true })
            }).catch(() => {
              next()
            })
          })
      } else {
        const routeMode = store.state.permission.routeMode
        if (routeMode !== 'authenticated') {
          installGeneratedRoutes('GenerateRoutes', { token }).then(() => {
            next({ ...to, replace: true })
          }).catch(() => {
            next()
          })
        } else {
          next()
        }
      }
    }
  } else {
    if (allowList.includes(to.name)) {
      next()
    } else if (isPublicPath(to.fullPath || to.path)) {
      if (store.state.permission.routeMode === 'guest') {
        next()
      } else {
        installGeneratedRoutes('GenerateGuestRoutes').then(() => {
          next({ ...to, replace: true })
        }).catch(() => {
          next({ path: '/404' })
        })
      }
    } else {
      if (isAuthModalReady()) {
        openAuthModal({ redirect: to.fullPath })
        const fromTitle = from.meta && from.meta.title
        setDocumentTitle(fromTitle ? `${i18nRender(fromTitle)} - ${domTitle}` : domTitle)
        next(false)
        NProgress.done()
      } else {
        next({ path: loginRoutePath, query: { redirect: to.fullPath } })
        NProgress.done() // if current page is login will not trigger afterEach hook, so manually handle it
      }
    }
  }
})

router.afterEach(() => {
  NProgress.done() // finish progress bar
})
