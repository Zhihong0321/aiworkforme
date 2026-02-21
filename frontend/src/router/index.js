import { createRouter, createWebHistory } from 'vue-router'
import Inbox from '../views/Inbox.vue'
import Leads from '../views/Leads.vue'
import Strategy from '../views/Strategy.vue'
import Knowledge from '../views/Knowledge.vue'
import Analytics from '../views/Analytics.vue'
import Playground from '../views/Playground.vue'
import Settings from '../views/Settings.vue'
import ChannelSetup from '../views/ChannelSetup.vue'
import Catalog from '../views/Catalog.vue'
import Calendar from '../views/Calendar.vue'
import Agents from '../views/Agents.vue'
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
    component: Agents,
    meta: { requiresAuth: true }
  },
  {
    path: '/inbox',
    name: 'Inbox',
    component: Inbox,
    meta: { requiresAuth: true }
  },
  {
    path: '/leads',
    name: 'Leads',
    component: Leads,
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
    name: 'Knowledge',
    component: Knowledge,
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
  routes
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
