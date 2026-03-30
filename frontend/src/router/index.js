import { createRouter, createWebHistory } from 'vue-router'
import Strategy from '../views/Strategy.vue'
import Analytics from '../views/Analytics.vue'
import Playground from '../views/Playground.vue'
import Settings from '../views/Settings.vue'
import ChannelSetup from '../views/ChannelSetup.vue'
import Catalog from '../views/Catalog.vue'
import Calendar from '../views/Calendar.vue'
import AgentsHome from '../views/AgentsHome.vue'
import AgentDashboard from '../views/AgentDashboard.vue'
import Login from '../views/Login.vue'
import PlatformLogin from '../views/PlatformLogin.vue'
import MessageHistory from '../views/MessageHistory.vue'
import ModelBenchmark from '../views/ModelBenchmark.vue'
import AICrmControl from '../views/AICrmControl.vue'
import Home from '../views/Home.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { bare: true }
  },
  {
    path: '/platform/login',
    name: 'Platform Login',
    component: PlatformLogin,
    meta: { bare: true }
  },
  {
    path: '/',
    redirect: '/home'
  },
  {
    path: '/home',
    name: 'Home',
    component: Home,
    meta: { requiresAuth: true }
  },
  {
    path: '/agents',
    name: 'Agents',
    component: AgentsHome,
    meta: { requiresAuth: true }
  },
  {
    path: '/agents/:agentId',
    name: 'Agent Dashboard',
    component: AgentDashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/inbox',
    redirect: () => {
      const activeAgentId = window.localStorage.getItem('activeAgentId')
      return activeAgentId ? `/agents/${activeAgentId}?tab=inbox` : '/agents'
    },
    meta: { requiresAuth: true }
  },
  {
    path: '/leads',
    redirect: () => {
      const activeAgentId = window.localStorage.getItem('activeAgentId')
      return activeAgentId ? `/agents/${activeAgentId}?tab=contacts` : '/agents'
    },
    meta: { requiresAuth: true }
  },
  {
    path: '/strategy',
    name: 'Strategy',
    component: Strategy,
    meta: { requiresAuth: true }
  },
  {
    path: '/knowledge',
    redirect: () => {
      const activeAgentId = window.localStorage.getItem('activeAgentId')
      return activeAgentId ? `/agents/${activeAgentId}?tab=knowledge` : '/agents'
    },
    meta: { requiresAuth: true }
  },
  {
    path: '/analytics',
    name: 'Analytics',
    component: Analytics,
    meta: { requiresAuth: true }
  },
  {
    path: '/playground',
    name: 'Playground',
    component: Playground,
    meta: { bare: false, requiresAuth: true }
  },
  {
    path: '/catalog',
    name: 'Catalog',
    component: Catalog,
    meta: { requiresAuth: true }
  },
  {
    path: '/channels',
    name: 'Channel Setup',
    component: ChannelSetup,
    meta: { requiresAuth: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
    meta: { requiresAuth: true, requiresPlatformAdmin: true }
  },
  {
    path: '/settings/history',
    name: 'Message History',
    component: MessageHistory,
    meta: { requiresAuth: true, requiresPlatformAdmin: true }
  },
  {
    path: '/settings/benchmark',
    name: 'Model Benchmark',
    component: ModelBenchmark,
    meta: { requiresAuth: true, requiresPlatformAdmin: true }
  },
  {
    path: '/calendar',
    name: 'Calendar',
    component: Calendar,
    meta: { requiresAuth: true }
  },
  {
    path: '/ai-crm',
    name: 'AI Control CRM',
    component: AICrmControl,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) {
      return { el: to.hash, behavior: 'smooth' }
    }
    return { top: 0 }
  }
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const roleFlag = localStorage.getItem('is_platform_admin')
  const isPlatformAdmin = roleFlag === 'true'

  if (to.meta.requiresAuth && !token) {
    next(to.meta.requiresPlatformAdmin ? '/platform/login' : '/login')
    return
  }

  if (to.meta.requiresPlatformAdmin && !isPlatformAdmin) {
    next('/platform/login')
    return
  }

  next()
})

export default router
