<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from '../composables/theme'
import { store } from '../store'

const route = useRoute()
const router = useRouter()
const { theme } = useTheme()

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('tenant_id')
  localStorage.removeItem('user_id')
  localStorage.removeItem('is_platform_admin')
  router.push('/login')
}
const isDark = computed(() => theme.value === 'dark')
const isPlatformAdmin = computed(() => localStorage.getItem('is_platform_admin') === 'true')

const isActive = (path) => {
  return route.path.startsWith(path)
}

const navItems = computed(() => {
  if (isPlatformAdmin.value) {
    return [{ label: 'System Settings', path: '/settings' }]
  }
  return [
    { label: 'My AI Agent', path: '/agents' },
    { label: 'Playground', path: '/playground' },
    { label: 'Contact Book', path: '/leads' },
    { label: 'Catalog', path: '/catalog' },
    { label: 'Knowledge', path: '/knowledge' },
    { label: 'Calendar', path: '/calendar' },
    { label: 'Channel Setup', path: '/channels' }
  ]
})

onMounted(() => {
  if (!isPlatformAdmin.value) {
    store.fetchWorkspaces()
  }
})
</script>

<template>
  <header
    :class="[
      'border-b sticky top-0 z-50',
      isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-300'
    ]"
  >
    <div class="mx-auto flex max-w-7xl items-center justify-between px-4">
      <div class="flex items-center py-3">
         <span class="text-sm font-black uppercase tracking-[0.2em] select-none" :class="isDark ? 'text-white' : 'text-black'">
            Aiworkfor.me
         </span>
      </div>

      <nav class="flex overflow-x-auto">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'px-4 py-4 text-[10px] font-bold uppercase tracking-[0.2em] -ml-px border-l border-r transition-all duration-200 whitespace-nowrap',
            'first:border-l',
            isDark ? 'border-slate-800' : 'border-gray-200',
            isActive(item.path)
              ? isDark
                ? 'bg-slate-800 text-white'
                : 'bg-black text-white border-black'
              : isDark
                ? 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                : 'bg-white text-gray-500 hover:bg-gray-50 hover:text-gray-900'
          ]"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="hidden sm:flex items-center gap-4">
        <span v-if="!isPlatformAdmin" class="text-[9px] font-bold uppercase tracking-widest" :class="store.activeWorkspace?.budget_tier === 'RED' ? 'text-red-500' : 'text-green-500'">
           ● {{ store.activeWorkspace?.budget_tier || 'GREEN' }} TIER
        </span>
        <button 
          @click="handleLogout"
          class="text-[9px] font-bold uppercase tracking-[0.2em] px-3 py-1.5 rounded-full border border-red-200 text-red-500 hover:bg-red-50 transition-all duration-200"
        >
          Logout
        </button>
      </div>
    </div>
  </header>
</template>
