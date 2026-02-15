<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme } from '../composables/theme'
import { store } from '../store'

const route = useRoute()
const { theme } = useTheme()
const isDark = computed(() => theme.value === 'dark')

const isActive = (path) => {
  return route.path.startsWith(path)
}

const navItems = [
  { label: 'Inbox', path: '/inbox' },
  { label: 'Leads', path: '/leads' },
  { label: 'Strategy', path: '/strategy' },
  { label: 'Knowledge', path: '/knowledge' },
  { label: 'Analytics', path: '/analytics' },
  { label: 'Playground', path: '/playground' },
  { label: 'Settings', path: '/settings' }
]

onMounted(() => {
  store.fetchWorkspaces()
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
         <span class="text-xs font-black uppercase tracking-[0.2em] mr-8 select-none" :class="isDark ? 'text-white' : 'text-black'">
            Aiworkfor.me
         </span>
         
         <!-- REAL WORKSPACE SELECTOR -->
         <select 
           v-if="store.workspaces.length > 0"
           :value="store.activeWorkspaceId"
           @change="e => store.setActiveWorkspace(e.target.value)"
           class="text-[10px] font-bold uppercase bg-transparent border-none focus:ring-0 cursor-pointer"
           :class="isDark ? 'text-slate-400' : 'text-slate-600'"
         >
           <option v-for="ws in store.workspaces" :key="ws.id" :value="ws.id">
             {{ ws.name }}
           </option>
         </select>
         <span v-else-if="store.isLoading" class="text-[10px] text-slate-400 animate-pulse">Loading...</span>
         <span v-else class="text-[10px] text-red-400">No Workspaces Found</span>
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
        <span class="text-[9px] font-bold uppercase tracking-widest" :class="store.activeWorkspace?.budget_tier === 'RED' ? 'text-red-500' : 'text-green-500'">
           ● {{ store.activeWorkspace?.budget_tier || 'GREEN' }} TIER
        </span>
      </div>
    </div>
  </header>
</template>
