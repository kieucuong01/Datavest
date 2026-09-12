// eslint-disable-next-line
import { UserLayout, BasicLayout, BlankLayout } from '@/layouts'

export const asyncRouterMap = [
  {
    path: '/',
    name: 'index',
    component: BasicLayout,
    meta: { title: 'menu.home', access: 'public' },
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
        meta: { title: 'menu.dashboard.aiAssetAnalysis', keepAlive: true, icon: 'appstore', permission: ['dashboard'], access: 'authenticated' }
      },
      // Strategy IDE.
      {
        path: '/strategy-ide',
        name: 'StrategyIDE',
        component: () => import('@/views/strategy-ide'),
        meta: { title: 'menu.dashboard.strategyIde', keepAlive: true, icon: 'code', permission: ['dashboard'], access: 'authenticated' }
      },
      {
        path: '/backtest-center',
        name: 'BacktestCenter',
        component: () => import('@/views/backtest-center'),
        meta: { title: 'menu.dashboard.backtestCenter', keepAlive: true, icon: 'bar-chart', permission: ['dashboard'], access: 'authenticated' }
      },
      {
        path: '/indicator-ide',
        name: 'IndicatorIDE',
        component: () => import('@/views/indicator-entry'),
        meta: { title: 'menu.dashboard.indicatorIde', keepAlive: true, icon: 'line-chart', permission: ['dashboard'], access: 'public' }
      },
      {
        path: '/smart-insights',
        name: 'SmartInsights',
        component: () => import('@/views/smart-insights'),
        meta: { title: 'menu.dashboard.smartInsights', keepAlive: true, icon: 'bulb', permission: ['dashboard'], access: 'public' }
      },
      {
        path: '/portfolio-optimizer',
        name: 'PortfolioOptimizer',
        component: () => import('@/views/portfolio-optimizer'),
        meta: { title: 'menu.dashboard.portfolioOptimizer', keepAlive: true, icon: 'fund', permission: ['dashboard'], access: 'authenticated' }
      },
      {
        path: '/menu-group/quant-lab',
        name: 'QuantLabMenu',
        redirect: '/portfolio-optimizer',
        hidden: true,
        meta: { title: 'menu.group.quantLab', keepAlive: false, icon: 'experiment', permission: ['dashboard'], access: 'authenticated' }
      },
      {
        path: '/universe-manager',
        name: 'UniverseManager',
        component: () => import('@/views/universe-manager'),
        hidden: true,
        meta: { title: 'menu.dashboard.universeManager', keepAlive: true, icon: 'database', permission: ['dashboard'], access: 'authenticated' }
      },
      // Legacy chart route.
      {
        path: '/indicator-analysis',
        name: 'Indicator',
        redirect: '/indicator-ide',
        hidden: true,
        meta: { title: 'menu.dashboard.indicator', keepAlive: false, icon: 'line-chart', permission: ['dashboard'], access: 'public' }
      },
      // Legacy dashboard route.
      {
        path: '/dashboard',
        name: 'Dashboard',
        redirect: '/strategy-ide',
        hidden: true,
        meta: { title: 'menu.dashboard', keepAlive: false, icon: 'dashboard', permission: ['dashboard'], access: 'authenticated' }
      },
      // Hidden AI analysis route.
      {
        path: '/ai-analysis/:pageNo([1-9]\\d*)?',
        name: 'Analysis',
        component: () => import('@/views/ai-analysis'),
        hidden: true,
        meta: { title: 'menu.dashboard.analysis', keepAlive: false, icon: 'thunderbolt', permission: ['dashboard'], access: 'authenticated' }
      },
      // User-facing paper portfolio workspace.
      {
        path: '/portfolio',
        name: 'Portfolio',
        component: () => import('@/views/mock-portfolio'),
        meta: { title: 'menu.dashboard.portfolio', keepAlive: false, icon: 'fund', permission: ['dashboard'], access: 'authenticated' }
      },
      // User profile. Admin-only items follow the menu divider.
      {
        path: '/profile',
        name: 'Profile',
        component: () => import('@/views/profile'),
        meta: { title: 'menu.myProfile', keepAlive: false, icon: 'user', permission: ['dashboard'], menuDividerAfter: true, access: 'authenticated' }
      },
      {
        path: '/ai-skills',
        name: 'AiSkills',
        component: () => import('@/views/ai-skills'),
        meta: { title: 'menu.aiSkills', keepAlive: false, icon: 'experiment', permission: ['admin'], access: 'authenticated' }
      },
      // System settings. Keep it last in the admin menu.
      {
        path: '/settings',
        name: 'Settings',
        component: () => import('@/views/settings'),
        meta: { title: 'menu.settings', keepAlive: false, icon: 'setting', permission: ['admin'], access: 'authenticated' }
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
    meta: { access: 'authenticated' },
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
    meta: { access: 'public' },
    children: [
      {
        path: 'login',
        name: 'login',
        component: () => import(/* webpackChunkName: "user" */ '@/views/user/Login'),
        meta: { access: 'public' }
      }
    ]
  },

  {
    path: '/404',
    meta: { title: 'menu.exception.not-find', access: 'public' },
    component: () => import(/* webpackChunkName: "fail" */ '@/views/exception/404')
  }
]
