<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme } from '../composables/theme'

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
  { label: 'Playground', path: '/playground' }
]
</script>

<template>
  <header
    :class="[
      'border-b',
      isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-300'
    ]"
  >
    <div class="mx-auto flex max-w-7xl items-center justify-between px-4">
      <div class="flex items-center py-3">
         <span class="text-xs font-black uppercase tracking-[0.2em] mr-8 select-none" :class="isDark ? 'text-white' : 'text-black'">
            Eternalgy
         </span>
      </div>
      <nav class="flex">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'px-6 py-4 text-[10px] font-bold uppercase tracking-[0.2em] -ml-px border-l border-r transition-all duration-200',
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
      <div class="flex items-center gap-4">
        <span class="text-[9px] font-bold uppercase tracking-widest text-green-500">
           ● GREEN TIER
        </span>
      </div>
    </div>
  </header>
</template>
