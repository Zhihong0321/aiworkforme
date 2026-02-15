import { createRouter, createWebHistory } from 'vue-router'
import Inbox from '../views/Inbox.vue'
import Leads from '../views/Leads.vue'
import Strategy from '../views/Strategy.vue'
import Knowledge from '../views/Knowledge.vue'
import Analytics from '../views/Analytics.vue'
import Playground from '../views/Playground.vue'

const routes = [
  {
    path: '/',
    redirect: '/inbox'
  },
  {
    path: '/inbox',
    name: 'Inbox',
    component: Inbox
  },
  {
    path: '/leads',
    name: 'Leads',
    component: Leads
  },
  {
    path: '/strategy',
    name: 'Strategy',
    component: Strategy
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: Knowledge
  },
  {
    path: '/analytics',
    name: 'Analytics',
    component: Analytics
  },
  {
    path: '/playground',
    name: 'Playground',
    component: Playground,
    meta: { bare: false }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
