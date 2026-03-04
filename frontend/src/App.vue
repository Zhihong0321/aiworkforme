<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TopNav from './components/TopNav.vue'

const route = useRoute()
const showNav = computed(() => !route.meta?.bare)
</script>

<template>
  <div class="min-h-screen bg-[var(--bg)] text-[var(--text)] font-display antialiased">
    <TopNav v-if="showNav" />
    <main class="flex flex-col p-4 max-w-4xl mx-auto w-full mt-4">
        <router-view />
    </main>
  </div>
</template>
