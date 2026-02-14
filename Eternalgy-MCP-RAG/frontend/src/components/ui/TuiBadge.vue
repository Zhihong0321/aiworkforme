<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'muted'
  }
})

const variants = {
  success:
    'border-[#1f1f1f] bg-[#1f1f1f] text-white',
  info:
    'border-[var(--border-strong)] bg-white text-[var(--text)]',
  warning:
    'border-[var(--border-strong)] bg-[var(--accent-soft)] text-[var(--text)]',
  muted:
    'border-[var(--border)] bg-white text-[var(--muted)]'
}

const classes = computed(() => [
  'inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs font-semibold uppercase tracking-wider',
  variants[props.variant] || variants.muted
])
</script>

<template>
  <span :class="classes">
    <slot />
  </span>
</template>
