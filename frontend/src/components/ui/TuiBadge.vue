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
    'border-success/25 bg-success/10 text-success',
  info:
    'border-line-strong bg-surface-elevated/90 text-ink',
  warning:
    'border-warning/25 bg-warning/10 text-warning',
  muted:
    'border-line bg-surface/80 text-ink-muted',
  danger:
    'border-danger/30 bg-danger/10 text-danger'
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
