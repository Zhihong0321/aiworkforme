<script setup>
const props = defineProps({
  title: String,
  subtitle: String
})
</script>

<template>
  <div class="border-b border-slate-200 px-5 py-6">
    <header v-if="title || subtitle" class="mb-4 flex items-start justify-between gap-3">
      <div class="space-y-1">
        <p v-if="subtitle" class="text-xs uppercase tracking-wider text-slate-500">
          {{ subtitle }}
        </p>
        <h3 v-if="title" class="text-lg font-semibold text-slate-900">{{ title }}</h3>
      </div>
      <div class="flex items-center gap-2">
        <slot name="actions" />
      </div>
    </header>
    <div>
      <slot />
    </div>
  </div>
</template>
