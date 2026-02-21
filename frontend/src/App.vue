<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import TopNav from './components/TopNav.vue'

const route = useRoute()
const showNav = computed(() => !route.meta?.bare)
</script>

<template>
  <div class="min-h-screen bg-[var(--bg)] text-[var(--text)]">
    <TopNav v-if="showNav" />
    <router-view />
  </div>
</template>
