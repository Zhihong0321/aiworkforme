<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'primary'
  },
  size: {
    type: String,
    default: 'md'
  },
  block: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const base =
  'inline-flex items-center justify-center gap-2 rounded-xl border font-semibold uppercase tracking-[0.12em] transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-primary/20 active:translate-y-[1px] select-none disabled:cursor-not-allowed disabled:opacity-60'

const variants = {
  primary:
    'border-primary-strong bg-primary text-primary-foreground shadow-[0_18px_30px_-18px_rgb(var(--accent-rgb)_/_0.55)] hover:border-primary-strong hover:bg-primary-strong',
  outline:
    'border-line-strong bg-surface-elevated/90 text-ink shadow-[0_16px_24px_-24px_rgb(var(--text-rgb)_/_0.55)] hover:bg-primary/10',
  ghost: 'border-transparent bg-transparent text-ink hover:bg-primary/10'
}

const sizes = {
  sm: 'px-3 py-2 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-3 text-base'
}

const classes = computed(() => [
  base,
  variants[props.variant] || variants.primary,
  sizes[props.size] || sizes.md,
  props.block ? 'w-full' : ''
])

</script>

<template>
  <button :class="classes" :disabled="loading">
    <span class="relative flex items-center gap-2">
      <span
        v-if="loading"
        class="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.2em]"
      >
        <span class="dot-pulse"></span>
        <span class="dot-pulse" style="animation-delay: 0.08s"></span>
        <span class="dot-pulse" style="animation-delay: 0.16s"></span>
      </span>
      <slot v-else />
    </span>
  </button>
</template>
<style scoped>
.dot-pulse {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: currentColor;
  display: inline-block;
  animation: pulse 0.9s ease-in-out infinite;
}

@keyframes pulse {
  0% {
    opacity: 0.3;
    transform: translateY(0);
  }
  50% {
    opacity: 1;
    transform: translateY(-2px);
  }
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }
}
</style>
