<script setup>
const props = defineProps({
  title: String,
  subtitle: String
})
</script>

<template>
  <div class="surface-card rounded-[1.75rem] px-5 py-6">
    <header v-if="title || subtitle" class="mb-4 flex items-start justify-between gap-3">
      <div class="space-y-1">
        <p v-if="subtitle" class="text-xs uppercase tracking-[0.22em] text-ink-subtle">
          {{ subtitle }}
        </p>
        <h3 v-if="title" class="text-lg font-semibold text-ink">{{ title }}</h3>
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
