<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { getNavItems } from '../config/navigation'

const router = useRouter()
const isPlatformAdmin = computed(() => localStorage.getItem('is_platform_admin') === 'true')

const quickLinks = computed(() => getNavItems(isPlatformAdmin.value).filter((item) => item.path !== '/home'))

const openPage = (path) => {
  router.push(path)
}
</script>

<template>
  <div class="home-shell min-h-[calc(100vh-64px)] px-4 pb-8 pt-5 sm:px-6">
    <section class="mx-auto max-w-5xl">
      <section class="home-card rounded-3xl p-4 sm:p-6">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-sm font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
            Quick Access
          </h2>
          <span class="text-xs text-[var(--muted)]">{{ quickLinks.length }} pages</span>
        </div>

        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <button
            v-for="item in quickLinks"
            :key="item.path"
            type="button"
            class="home-link group text-left"
            @click="openPage(item.path)"
          >
            <div class="flex items-center justify-between gap-3">
              <h3 class="text-base font-semibold text-[var(--text)]">{{ item.label }}</h3>
              <span class="text-[var(--muted)] transition-transform duration-200 group-hover:translate-x-1">→</span>
            </div>
            <p class="mt-1 text-xs leading-relaxed text-[var(--muted)]">
              {{ item.description }}
            </p>
          </button>
        </div>
      </section>
    </section>
  </div>
</template>

<style scoped>
.home-shell {
  background:
    radial-gradient(circle at 18% 12%, rgba(15, 23, 42, 0.05), transparent 40%),
    radial-gradient(circle at 85% 10%, rgba(30, 64, 175, 0.08), transparent 42%),
    var(--bg);
}

.home-card {
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
}

.home-link {
  border-radius: 1rem;
  border: 1px solid var(--border);
  background: #fff;
  padding: 0.9rem;
  transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}

.home-link:hover {
  border-color: var(--border-strong);
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
}

.home-link:active {
  transform: translateY(1px);
}
</style>
