// eslint-disable-next-line
import { UserLayout, BasicLayout, BlankLayout } from '@/layouts'

export const asyncRouterMap = [
  {
    path: '/',
    name: 'index',
    component: BasicLayout,
    meta: { title: 'menu.home' },
    redirect: '/smart-insights',
    children: [
      // AI asset analysis landing page.
      // keepAlive: true so the heavy market-data fetches (sentiment / indices /
      // heatmap / calendar / opportunities / watchlist prices) only run on the
      // first visit. The component handles its own "data is stale" refresh in
      // `activated()`. Disabling this again will reintroduce a 1~3s cold start
      // every time the user navigates back here.
      {
        path: '/ai-asset-analysis',
        name: 'AIAssetAnalysis',
        component: () => import('@/views/ai-asset-analysis'),
        meta: { title: 'menu.dashboard.aiAssetAnalysis', keepAlive: true, icon: 'appstore', permission: ['dashboard'] }
      },
      // Strategy IDE.
      {
        path: '/strategy-ide',
        name: 'StrategyIDE',
        component: () => import('@/views/strategy-ide'),
        meta: { title: 'menu.dashboard.strategyIde', keepAlive: true, icon: 'code', permission: ['dashboard'] }
      },
      {
        path: '/backtest-center',
        name: 'BacktestCenter',
        component: () => import('@/views/backtest-center'),
        meta: { title: 'menu.dashboard.backtestCenter', keepAlive: true, icon: 'bar-chart', permission: ['dashboard'] }
      },
      {
        path: '/indicator-ide',
        name: 'IndicatorIDE',
        component: () => import('@/views/indicator-ide'),
        meta: { title: 'menu.dashboard.indicatorIde', keepAlive: true, icon: 'line-chart', permission: ['dashboard'] }
      },
      {
        path: '/smart-insights',
        name: 'SmartInsights',
        component: () => import('@/views/smart-insights'),
        meta: { title: 'menu.dashboard.smartInsights', keepAlive: true, icon: 'bulb', permission: ['dashboard'] }
      },
      {
        path: '/portfolio-optimizer',
        name: 'PortfolioOptimizer',
        component: () => import('@/views/portfolio-optimizer'),
        meta: { title: 'menu.dashboard.portfolioOptimizer', keepAlive: true, icon: 'fund', permission: ['dashboard'] }
      },
      {
        path: '/menu-group/quant-lab',
        name: 'QuantLabMenu',
        redirect: '/portfolio-optimizer',
        hidden: true,
        meta: { title: 'menu.group.quantLab', keepAlive: false, icon: 'experiment', permission: ['dashboard'] }
      },
      {
        path: '/universe-manager',
        name: 'UniverseManager',
        component: () => import('@/views/universe-manager'),
        hidden: true,
        meta: { title: 'menu.dashboard.universeManager', keepAlive: true, icon: 'database', permission: ['dashboard'] }
      },
      // Legacy chart route.
      {
        path: '/indicator-analysis',
        name: 'Indicator',
        redirect: '/indicator-ide',
        hidden: true,
        meta: { title: 'menu.dashboard.indicator', keepAlive: false, icon: 'line-chart', permission: ['dashboard'] }
      },
      // Legacy dashboard route.
      {
        path: '/dashboard',
        name: 'Dashboard',
        redirect: '/strategy-ide',
        hidden: true,
        meta: { title: 'menu.dashboard', keepAlive: false, icon: 'dashboard', permission: ['dashboard'] }
      },
      // Hidden AI analysis route.
      {
        path: '/ai-analysis/:pageNo([1-9]\\d*)?',
        name: 'Analysis',
        component: () => import('@/views/ai-analysis'),
        hidden: true,
        meta: { title: 'menu.dashboard.analysis', keepAlive: false, icon: 'thunderbolt', permission: ['dashboard'] }
      },
      // Legacy portfolio bookmarks now open the unified live workspace.
      {
        path: '/portfolio',
        name: 'Portfolio',
        redirect: '/portfolio-optimizer',
        hidden: true,
        meta: { title: 'menu.dashboard.portfolio', keepAlive: false, icon: 'fund', permission: ['dashboard'] }
      },
      // User profile. Admin-only items follow the menu divider.
      {
        path: '/profile',
        name: 'Profile',
        component: () => import('@/views/profile'),
        meta: { title: 'menu.myProfile', keepAlive: false, icon: 'user', permission: ['dashboard'], menuDividerAfter: true }
      },
      {
        path: '/ai-skills',
        name: 'AiSkills',
        component: () => import('@/views/ai-skills'),
        meta: { title: 'menu.aiSkills', keepAlive: false, icon: 'experiment', permission: ['admin'] }
      },
      // System settings. Keep it last in the admin menu.
      {
        path: '/settings',
        name: 'Settings',
        component: () => import('@/views/settings'),
        meta: { title: 'menu.settings', keepAlive: false, icon: 'setting', permission: ['admin'] }
      }
    ]
  },
  {
    path: '*',
    redirect: '/404',
    hidden: true
  }
]

/**
 * Base routes.
 * @type { *[] }
 */
export const constantRouterMap = [
  {
    path: '/strategy-runtime',
    hidden: true,
    redirect: to => ({
      path: '/strategy-ide',
      query: to.query && to.query.strategy_id ? { strategy_id: to.query.strategy_id } : {}
    })
  },
  {
    path: '/user',
    component: UserLayout,
    redirect: '/user/login',
    hidden: true,
    children: [
      {
        path: 'login',
        name: 'login',
        component: () => import(/* webpackChunkName: "user" */ '@/views/user/Login')
      }
    ]
  },

  {
    path: '/404',
    meta: { title: 'menu.exception.not-find' },
    component: () => import(/* webpackChunkName: "fail" */ '@/views/exception/404')
  }
]
