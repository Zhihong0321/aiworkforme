<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TopNav from './components/TopNav.vue'

const route = useRoute()
const showNav = computed(() => !route.meta?.bare)
const mainClasses = computed(() =>
  showNav.value
    ? 'relative z-10 mx-auto flex w-full max-w-5xl flex-col px-4 pb-8 pt-4 sm:px-6'
    : 'relative z-10 flex min-h-screen flex-col'
)
</script>

<template>
  <div class="min-h-screen bg-[var(--bg)] text-[var(--text)] font-display antialiased">
    <div class="pointer-events-none fixed inset-x-0 top-0 h-72 bg-[radial-gradient(circle_at_top,_rgb(var(--accent-rgb)_/_0.18),_transparent_62%)]"></div>
    <div class="pointer-events-none fixed bottom-0 right-0 h-56 w-56 rounded-full bg-[rgb(var(--border-strong-rgb)_/_0.10)] blur-3xl"></div>
    <TopNav v-if="showNav" />
    <main :class="mainClasses">
      <router-view />
    </main>
  </div>
</template>
