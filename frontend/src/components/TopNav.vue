<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from '../composables/theme'
import { store } from '../store'

const route = useRoute()
const router = useRouter()
const { theme } = useTheme()

const isMobileMenuOpen = ref(false)
const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

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
    return [
      { label: 'System Settings', path: '/settings' },
      { label: 'Message History', path: '/settings/history' },
      { label: 'Model Benchmark', path: '/settings/benchmark' }
    ]
  }
  return [
    { label: 'My AI Agent', path: '/agents' },
    { label: 'Playground', path: '/playground' },
    { label: 'Contact Book', path: '/leads' },
    { label: 'AI Control CRM', path: '/ai-crm' },
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
      'border-b sticky top-0 z-50 transition-colors',
      isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-300'
    ]"
  >
    <div class="mx-auto flex max-w-7xl items-center justify-between px-4 h-16 mt-0">
      <div class="flex items-center">
         <span class="text-sm font-black uppercase tracking-[0.2em] select-none" :class="isDark ? 'text-white' : 'text-black'">
            Aiworkfor.me
         </span>
      </div>

      <!-- Desktop Nav -->
      <nav class="hidden lg:flex flex-1 justify-center overflow-x-auto mx-4">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'px-3 py-4 text-[10px] font-bold uppercase tracking-[0.2em] -ml-px border-l border-r transition-all duration-200 whitespace-nowrap',
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

      <!-- Desktop Actions -->
      <div class="hidden lg:flex items-center gap-4">
        <span v-if="!isPlatformAdmin" class="text-[9px] font-bold uppercase tracking-widest whitespace-nowrap" :class="store.activeWorkspace?.budget_tier === 'RED' ? 'text-red-500' : 'text-green-500'">
           ● {{ store.activeWorkspace?.budget_tier || 'GREEN' }} TIER
        </span>
        <button 
          @click="handleLogout"
          class="text-[9px] font-bold uppercase tracking-[0.2em] px-3 py-1.5 rounded-full border border-red-200 text-red-500 hover:bg-red-50 transition-all duration-200 whitespace-nowrap"
        >
          Logout
        </button>
      </div>

      <!-- Mobile Menu Button -->
      <div class="flex lg:hidden items-center">
        <button 
          @click="toggleMobileMenu"
          :class="['p-2 rounded-md', isDark ? 'text-slate-400 hover:text-white hover:bg-slate-800' : 'text-gray-600 hover:text-black hover:bg-gray-100']"
        >
          <span class="sr-only">Open main menu</span>
          <!-- Hamburger -->
          <svg v-if="!isMobileMenuOpen" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <!-- Close -->
          <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile Nav -->
    <div v-show="isMobileMenuOpen" class="lg:hidden border-t" :class="isDark ? 'border-slate-800 bg-slate-900' : 'border-gray-200 bg-white'">
      <div class="px-2 pt-2 pb-3 space-y-1 max-h-[70vh] overflow-y-auto">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          @click="isMobileMenuOpen = false"
          :class="[
            'block px-3 py-3 rounded-md text-xs font-bold uppercase tracking-widest transition-colors',
            isActive(item.path)
              ? isDark ? 'bg-slate-800 text-white' : 'bg-black text-white'
              : isDark ? 'text-slate-400 hover:bg-slate-800 hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-900'
          ]"
        >
          {{ item.label }}
        </router-link>
      </div>
      <div class="pt-4 pb-3 border-t" :class="isDark ? 'border-slate-800' : 'border-gray-200'">
        <div class="px-5 flex items-center justify-between">
          <span v-if="!isPlatformAdmin" class="text-[10px] font-bold uppercase tracking-widest" :class="store.activeWorkspace?.budget_tier === 'RED' ? 'text-red-500' : 'text-green-500'">
             ● {{ store.activeWorkspace?.budget_tier || 'GREEN' }} TIER
          </span>
          <button 
            @click="handleLogout"
            class="text-[10px] font-bold uppercase tracking-[0.2em] px-4 py-2 rounded-full border border-red-200 text-red-500 hover:bg-red-50 transition-all duration-200"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
