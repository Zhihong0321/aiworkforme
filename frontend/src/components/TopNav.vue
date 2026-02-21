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
const showBackHome = computed(() => route.path !== '/home')

const toggleMobileMenu = () => {
  isMobileMenuOpen.value = !isMobileMenuOpen.value
}

const goHome = () => {
  isMobileMenuOpen.value = false
  router.push('/home')
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
    store.fetchWorkspaces()
  }
})
</script>

<template>
  <header class="topnav sticky top-0 z-50 border-b border-[var(--border)] bg-[rgba(255,255,255,0.92)] backdrop-blur">
    <div class="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
      <div class="flex items-center gap-2">
        <button
          v-if="showBackHome"
          type="button"
          class="inline-flex h-9 items-center rounded-lg border border-[var(--border)] px-2 text-xs font-semibold text-[var(--text)] transition hover:border-[var(--border-strong)] hover:bg-white sm:px-3"
          @click="goHome"
        >
          <span class="sm:hidden">←</span>
          <span class="hidden sm:inline">← Home</span>
        </button>
        <span class="select-none text-sm font-semibold uppercase tracking-[0.17em] text-[var(--text)]">
          Aiworkfor.me
        </span>
      </div>

      <nav class="hidden lg:flex lg:flex-1 lg:items-center lg:justify-center lg:gap-1 lg:overflow-x-auto">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'rounded-md px-3 py-2 text-[11px] font-medium uppercase tracking-[0.14em] transition-colors whitespace-nowrap',
            isActive(item.path)
              ? 'bg-[var(--text)] text-white'
              : 'text-[var(--muted)] hover:bg-white hover:text-[var(--text)]'
          ]"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="hidden items-center gap-3 lg:flex">
        <span
          v-if="!isPlatformAdmin"
          class="rounded-md border border-[var(--border)] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]"
          :class="store.activeWorkspace?.budget_tier === 'RED' ? 'text-red-600' : 'text-emerald-600'"
        >
          {{ store.activeWorkspace?.budget_tier || 'GREEN' }} Tier
        </span>
        <button
          type="button"
          class="h-9 rounded-lg border border-red-200 px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-red-600 transition hover:bg-red-50"
          @click="handleLogout"
        >
          Logout
        </button>
      </div>

      <button
        type="button"
        class="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--border)] text-[var(--muted)] transition hover:border-[var(--border-strong)] hover:text-[var(--text)] lg:hidden"
        @click="toggleMobileMenu"
      >
        <span class="sr-only">Toggle menu</span>
        <svg v-if="!isMobileMenuOpen" class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        <svg v-else class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <div v-show="isMobileMenuOpen" class="border-t border-[var(--border)] bg-white lg:hidden">
      <div class="space-y-1 px-3 pb-4 pt-3">
        <button
          v-if="showBackHome"
          type="button"
          class="flex w-full items-center rounded-md border border-[var(--border)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text)]"
          @click="goHome"
        >
          ← Back to Home
        </button>

        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'block rounded-md px-3 py-2 text-xs font-medium uppercase tracking-[0.12em] transition-colors',
            isActive(item.path)
              ? 'bg-[var(--text)] text-white'
              : 'text-[var(--muted)] hover:bg-[var(--accent-soft)] hover:text-[var(--text)]'
          ]"
        >
          {{ item.label }}
        </router-link>

        <div class="mt-2 border-t border-[var(--border)] pt-3">
          <span
            v-if="!isPlatformAdmin"
            class="mb-2 block text-[10px] font-semibold uppercase tracking-[0.12em]"
            :class="store.activeWorkspace?.budget_tier === 'RED' ? 'text-red-600' : 'text-emerald-600'"
          >
            {{ store.activeWorkspace?.budget_tier || 'GREEN' }} Tier
          </span>
          <button
            type="button"
            class="w-full rounded-md border border-red-200 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-red-600"
            @click="handleLogout"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
