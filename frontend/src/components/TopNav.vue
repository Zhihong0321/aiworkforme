<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { store } from '../store'
import { getNavItems } from '../config/navigation'

const route = useRoute()
const router = useRouter()

const isMobileMenuOpen = ref(false)
const isAgentMenuOpen = ref(false)
const agentMenuRef = ref(null)
const isPlatformAdmin = computed(() => localStorage.getItem('is_platform_admin') === 'true')
const navItems = computed(() => getNavItems(isPlatformAdmin.value))

const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

const toggleAgentMenu = () => {
  if (isPlatformAdmin.value) return
  isAgentMenuOpen.value = !isAgentMenuOpen.value
}

const closeAgentMenu = () => {
  isAgentMenuOpen.value = false
}

const goToAgents = () => {
  closeAgentMenu()
  router.push('/agents')
}

const selectAgent = (agentId) => {
  store.setActiveAgent(agentId)
  closeAgentMenu()
  router.push(`/agents/${agentId}`)
}

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('tenant_id')
  localStorage.removeItem('user_id')
  localStorage.removeItem('is_platform_admin')
  router.push('/login')
}

const isActive = (path) => {
  if (path.includes('#')) {
    const [basePath, hashPath] = path.split('#')
    const expectedHash = `#${hashPath}`
    if (route.path === basePath && !route.hash && expectedHash === '#overview') {
      return true
    }
    return route.path === basePath && route.hash === expectedHash
  }
  return route.path.startsWith(path)
}

watch(
  () => route.fullPath,
  () => {
    isMobileMenuOpen.value = false
    closeAgentMenu()
  }
)

const handleDocumentClick = (event) => {
  if (!agentMenuRef.value?.contains(event.target)) {
    closeAgentMenu()
  }
}

onMounted(() => {
  if (!isPlatformAdmin.value) {
    store.fetchAgents()
  }
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})

const activeAgentName = computed(() => store.activeAgent?.name || 'Aiworkfor.me')
const pageTitle = computed(() => {
  if (route.name === 'Agent Dashboard') {
    return store.activeAgent?.name || 'Agent Dashboard'
  }
  const matched = navItems.value.find((item) => isActive(item.path))
  if (matched) return matched.label
  return route.name || 'Overview'
})
</script>

<template>
  <div>
    <header v-if="isPlatformAdmin" class="sticky top-0 z-40 border-b border-line/70 bg-surface/86 px-4 py-3 backdrop-blur-xl sm:px-6 lg:px-8">
      <div class="mx-auto flex w-full max-w-[1800px] items-center justify-between gap-4">
        <div class="min-w-0">
          <p class="text-[10px] font-bold uppercase tracking-[0.3em] text-ink-subtle">Platform Admin Console</p>
          <h2 class="truncate text-lg font-black tracking-tight text-ink sm:text-xl">{{ pageTitle }}</h2>
        </div>

        <nav class="hidden xl:flex items-center gap-2 overflow-x-auto">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition-colors"
            :class="isActive(item.path) ? 'border-primary/20 bg-primary/10 text-primary' : 'border-line/70 bg-surface-elevated/90 text-ink-muted hover:border-line-strong hover:text-ink'"
          >
            <span class="material-symbols-outlined text-[18px]" :class="{'font-fill': isActive(item.path)}">{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </router-link>
        </nav>

        <div class="flex items-center gap-2">
          <button
            @click="handleLogout"
            class="inline-flex items-center gap-2 rounded-full border border-line/70 bg-surface-elevated/90 px-4 py-2 text-sm font-semibold text-ink-muted transition-colors hover:border-danger/30 hover:bg-danger/10 hover:text-danger"
          >
            <span class="material-symbols-outlined text-[18px]">logout</span>
            Logout
          </button>
        </div>
      </div>
    </header>

    <template v-else>
      <div v-show="isMobileMenuOpen" class="fixed inset-0 z-50 overflow-hidden" id="sidebar-drawer">
        <div class="absolute inset-0 bg-[rgb(var(--text-rgb)_/_0.42)] backdrop-blur-sm transition-opacity" @click="toggleMobileMenu"></div>
        <div class="absolute inset-y-0 left-0 flex w-full max-w-xs flex-col border-r border-line/80 bg-surface-elevated/95 px-1 shadow-2xl backdrop-blur-xl transition-transform duration-300" :class="isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'">
          <div class="border-b border-line/70 px-5 pb-5 pt-6">
            <div class="mb-4 flex items-center justify-between">
              <span class="text-xs font-bold uppercase tracking-[0.24em] text-ink-subtle">Workspace</span>
              <button class="rounded-full p-2 text-ink-subtle transition-colors hover:bg-surface-muted/80 hover:text-ink" @click="toggleMobileMenu">
                <span class="material-symbols-outlined">close</span>
              </button>
            </div>
            <div ref="agentMenuRef" class="relative">
              <button
                type="button"
                class="flex w-full items-center gap-3 rounded-[1.5rem] border border-line/90 bg-surface-muted/80 p-3.5 text-left transition-colors hover:border-line-strong hover:bg-surface-muted"
                @click.stop="toggleAgentMenu"
              >
                <div class="flex size-11 items-center justify-center rounded-full border border-primary/20 bg-primary/10 text-sm font-bold text-primary">
                  {{ activeAgentName.charAt(0).toUpperCase() }}
                </div>
                <div class="flex-1 overflow-hidden">
                  <p class="truncate font-bold text-ink">{{ activeAgentName }}</p>
                  <p class="text-xs text-ink-muted">Active now</p>
                </div>
                <span class="material-symbols-outlined text-ink-subtle">{{ isAgentMenuOpen ? 'expand_less' : 'unfold_more' }}</span>
              </button>

              <div v-if="isAgentMenuOpen" class="absolute left-0 top-[calc(100%+12px)] z-50 w-full rounded-2xl border border-line bg-surface-elevated p-1 shadow-panel">
                <button
                  v-for="agent in store.agents"
                  :key="agent.id"
                  type="button"
                  @click="selectAgent(agent.id)"
                  class="flex w-full items-center justify-between gap-3 rounded-xl px-4 py-2.5 text-left text-sm transition-colors hover:bg-primary/10"
                  :class="store.activeAgentId == agent.id ? 'font-bold text-primary' : 'text-ink-muted'"
                >
                  <span class="truncate">{{ agent.name }}</span>
                  <span v-if="store.activeAgentId == agent.id" class="material-symbols-outlined text-base">check</span>
                </button>

                <button
                  type="button"
                  @click="goToAgents"
                  class="mt-1 flex w-full items-center gap-2 rounded-xl border border-dashed border-line px-4 py-2.5 text-left text-sm font-semibold text-ink transition-colors hover:border-primary/40 hover:bg-primary/5"
                >
                  <span class="material-symbols-outlined text-base">settings</span>
                  <span>Manage agents</span>
                </button>
              </div>
            </div>
          </div>

          <nav class="flex-1 space-y-1 overflow-y-auto p-4">
            <router-link
              v-for="item in navItems"
              :key="item.path"
              :to="item.path"
              class="flex items-center gap-3 rounded-2xl px-4 py-3 transition-colors"
              :class="isActive(item.path) ? 'bg-primary/10 text-primary font-bold shadow-[inset_0_0_0_1px_rgb(var(--accent-rgb)_/_0.14)]' : 'text-ink-muted hover:bg-surface-muted/80 hover:text-ink'"
            >
              <span class="material-symbols-outlined" :class="{ 'font-fill': isActive(item.path) }">{{ item.icon }}</span>
              <div class="min-w-0">
                <span class="block truncate font-medium">{{ item.label }}</span>
                <span class="block truncate text-[11px] font-medium text-ink-subtle">{{ item.description }}</span>
              </div>
            </router-link>
          </nav>

          <div class="mt-auto space-y-1 border-t border-line/70 p-4">
            <button @click="handleLogout" class="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-ink-muted transition-colors hover:bg-danger/10 hover:text-danger">
              <span class="material-symbols-outlined">logout</span>
              <span class="font-medium">Logout</span>
            </button>
          </div>
        </div>
      </div>

      <header class="sticky top-0 z-40 mx-auto flex w-full max-w-5xl items-center justify-between border-b border-line/70 bg-surface/80 px-4 py-3 shadow-shell backdrop-blur-xl sm:px-6">
        <div class="flex items-center gap-4">
          <button @click="toggleMobileMenu" class="flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-line/80 bg-surface-elevated/90 text-ink shadow-[0_8px_20px_-16px_rgb(var(--text-rgb)_/_0.55)] transition-colors hover:border-line-strong hover:bg-surface-muted">
            <span class="material-symbols-outlined">menu</span>
          </button>
        </div>
        <div class="min-w-0 flex-1 px-4 text-center">
          <p class="text-[10px] font-bold uppercase tracking-[0.26em] text-ink-subtle">Aiworkfor.me</p>
          <h2 class="truncate text-base font-bold leading-tight tracking-[-0.015em] text-ink sm:text-lg">{{ pageTitle }}</h2>
        </div>
        <div class="flex w-11 items-center justify-end">
          <button class="relative flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-line/80 bg-surface-elevated/90 text-ink shadow-[0_8px_20px_-16px_rgb(var(--text-rgb)_/_0.55)] transition-colors hover:border-line-strong hover:bg-surface-muted">
            <span class="material-symbols-outlined">notifications</span>
            <span class="absolute right-3 top-3 h-2.5 w-2.5 rounded-full border border-surface-elevated bg-danger"></span>
          </button>
        </div>
      </header>
    </template>
  </div>
</template>
