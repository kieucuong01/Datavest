import { constantRouterMap } from '@/config/router.config'
import { generatorDynamicRouter, generatorGuestRouter } from '@/router/generator-routers'

const permission = {
  state: {
    routers: constantRouterMap,
    addRouters: [],
    routeMode: 'none'
  },
  mutations: {
    SET_ROUTERS: (state, routers) => {
      state.addRouters = routers
      state.routers = constantRouterMap.concat(routers)
      state.routeMode = 'authenticated'
    },
    SET_GUEST_ROUTERS: (state, routers) => {
      state.addRouters = routers
      state.routers = constantRouterMap.concat(routers)
      state.routeMode = 'guest'
    },
    // Reset routers to force regeneration (used on login/logout)
    RESET_ROUTERS: (state) => {
      state.addRouters = []
      state.routers = constantRouterMap
      state.routeMode = 'none'
    }
  },
  actions: {
    GenerateRoutes ({ commit, rootState }, data) {
      return new Promise((resolve, reject) => {
        const { token } = data
        generatorDynamicRouter(token).then(routers => {
          commit('SET_ROUTERS', routers)
          resolve()
        }).catch(e => {
          reject(e)
        })
      })
    },
    GenerateGuestRoutes ({ commit }) {
      return generatorGuestRouter().then(routers => {
        commit('SET_GUEST_ROUTERS', routers)
      })
    },
    // Reset routes action
    ResetRoutes ({ commit }) {
      commit('RESET_ROUTERS')
    }
  }
}

export default permission
