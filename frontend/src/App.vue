<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme } from './composables/theme'
import TopNav from './components/TopNav.vue'

const route = useRoute()
const { theme } = useTheme()
const isDark = computed(() => theme.value === 'dark')

const showNav = computed(() => !route.meta?.bare)
</script>

<template>
  <div
    :class="[
      'min-h-screen',
      isDark ? 'bg-[#0e0e10] text-[var(--text)]' : 'bg-[var(--bg)] text-[var(--text)]'
    ]"
  >
    <TopNav v-if="showNav" />
    <router-view />
  </div>
</template>
