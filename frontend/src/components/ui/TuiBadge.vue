<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'muted'
  },
  size: {
    type: String,
    default: 'md'
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
    'border-[var(--border)] bg-white text-[var(--muted)]',
  danger:
    'border-red-500/50 bg-red-500/10 text-red-500'
}

const sizes = {
  xs: 'px-1.5 py-0.5 text-[8px]',
  sm: 'px-2 py-0.5 text-[10px]',
  md: 'px-2.5 py-1 text-xs'
}

const classes = computed(() => [
  'inline-flex items-center gap-2 rounded-md border font-semibold uppercase tracking-wider transition-colors',
  variants[props.variant] || variants.muted,
  sizes[props.size] || sizes.md
])
</script>

<template>
  <span :class="classes">
    <slot />
  </span>
</template>
