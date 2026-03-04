<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { store } from '../store'
import { getNavItems } from '../config/navigation'

const route = useRoute()
const router = useRouter()

const isMobileMenuOpen = ref(false)
const isPlatformAdmin = computed(() => localStorage.getItem('is_platform_admin') === 'true')

const navItems = computed(() => getNavItems(isPlatformAdmin.value))

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

const isActive = (path) => route.path.startsWith(path)

watch(
  () => route.path,
  () => {
    isMobileMenuOpen.value = false
  }
)

onMounted(() => {
  if (!isPlatformAdmin.value) {
    store.fetchAgents()
  }
})

// Quick compute of the active agent initial
const activeAgentName = computed(() => {
    return store.activeAgent?.name || 'Aiworkfor.me'
})
const pageTitle = computed(() => {
    const matched = navItems.value.find(item => isActive(item.path))
    return matched ? matched.label : route.name || 'Overview'
})
</script>

<template>
  <div>
    <!-- Navigation Drawer Overlay -->
    <div 
        v-show="isMobileMenuOpen" 
        class="fixed inset-0 z-50 overflow-hidden" 
        id="sidebar-drawer"
    >
      <div 
          class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity"
          @click="toggleMobileMenu"
      ></div>
      <div 
          class="absolute inset-y-0 left-0 w-full max-w-xs bg-white dark:bg-slate-950 shadow-2xl flex flex-col transform transition-transform duration-300"
          :class="isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'"
      >
        <!-- Drawer Header / Agent Switcher -->
        <div class="p-6 border-b border-slate-100 dark:border-slate-800">
          <div class="flex items-center justify-between mb-4">
            <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Active Agent</span>
            <button class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200" @click="toggleMobileMenu">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>
          <div class="flex items-center gap-3 p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900 cursor-pointer transition-colors relative group">
            <div class="size-10 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold">
                {{ activeAgentName.charAt(0).toUpperCase() }}
            </div>
            <div class="flex-1 overflow-hidden" v-if="!isPlatformAdmin">
              <p class="font-bold text-slate-900 dark:text-slate-100 truncate">{{ activeAgentName }}</p>
              <p class="text-xs text-slate-500">Active Now</p>
            </div>
            <div class="flex-1 overflow-hidden" v-else>
               <p class="font-bold text-slate-900 dark:text-slate-100 truncate">Platform Admin</p>
            </div>
            <span class="material-symbols-outlined text-slate-400">unfold_more</span>
            
            <!-- Minimal dropdown for agent switching -->
            <div class="absolute top-[110%] left-0 w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl hidden group-hover:block z-50" v-if="!isPlatformAdmin && store.agents.length > 1">
                <div 
                    v-for="agent in store.agents" 
                    :key="agent.id"
                    @click="store.setActiveAgent(agent.id)"
                    class="px-4 py-2 hover:bg-slate-50 dark:hover:bg-slate-700 cursor-pointer text-sm truncate"
                    :class="{'font-bold text-primary': store.activeAgentId == agent.id}"
                >
                    {{ agent.name }}
                </div>
            </div>
          </div>
        </div>

        <!-- Drawer Links -->
        <nav class="flex-1 overflow-y-auto p-4 space-y-1">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="flex items-center gap-3 px-4 py-3 rounded-xl transition-colors"
            :class="isActive(item.path) ? 'bg-primary/10 text-primary font-bold' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'"
          >
            <span class="material-symbols-outlined" :class="{'font-fill': isActive(item.path)}">{{ item.icon }}</span>
            <span class="font-medium">{{ item.label }}</span>
          </router-link>
        </nav>

        <!-- Drawer Bottom Actions -->
        <div class="p-4 mt-auto border-t border-slate-100 dark:border-slate-800 space-y-1">
          <button @click="handleLogout" class="flex w-full items-center gap-3 px-4 py-3 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            <span class="material-symbols-outlined">logout</span>
            <span class="font-medium">Logout</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Top App Bar -->
    <header class="sticky top-0 z-40 flex items-center bg-white/80 dark:bg-slate-950/80 backdrop-blur-md p-4 justify-between border-b border-slate-200 dark:border-slate-800 max-w-4xl mx-auto">
      <div class="flex items-center gap-4">
        <button 
            @click="toggleMobileMenu" 
            class="text-slate-900 dark:text-slate-100 flex size-10 shrink-0 items-center justify-center rounded-full hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <span class="material-symbols-outlined">menu</span>
        </button>
      </div>
      <h2 class="text-slate-900 dark:text-slate-100 text-lg font-bold leading-tight tracking-[-0.015em] flex-1 text-center truncate px-4">
        {{ pageTitle }}
      </h2>
      <div class="flex items-center justify-end w-10">
        <button class="text-slate-900 dark:text-slate-100 flex size-10 shrink-0 items-center justify-center rounded-full hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors cursor-pointer relative">
          <span class="material-symbols-outlined">notifications</span>
          <span class="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full border border-white dark:border-slate-950"></span>
        </button>
      </div>
    </header>
  </div>
</template>
