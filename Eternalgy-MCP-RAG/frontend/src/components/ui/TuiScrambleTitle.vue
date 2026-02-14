<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  text: {
    type: String,
    required: true
  },
  duration: {
    type: Number,
    default: 1200 // total ms to resolve
  },
  intervalMs: {
    type: Number,
    default: 16 // ~60fps
  },
  glyphs: {
    type: String,
    default: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%&'
  },
  variant: {
    type: String,
    default: 'neon' // neon | mono | static
  }
})

const display = ref([])
const target = ref([])
const locked = ref(new Set())
let timer = null
let startedAt = 0

const reset = () => {
  target.value = props.text.split('')
  display.value = target.value.map(() => randomGlyph())
  locked.value = new Set()
  startedAt = performance.now()
}

const randomGlyph = () =>
  props.glyphs.charAt(Math.floor(Math.random() * props.glyphs.length)) || 'X'

const step = () => {
  const now = performance.now()
  const elapsed = now - startedAt
  const total = props.duration
  const progress = Math.min(1, total === 0 ? 1 : elapsed / total)
  const toLock = Math.floor(progress * target.value.length)

  const newLocked = new Set(locked.value)
  for (let i = 0; i < toLock; i += 1) {
    newLocked.add(i)
  }
  locked.value = newLocked

  display.value = target.value.map((char, idx) => {
    if (locked.value.has(idx) || char === ' ') return char
    return randomGlyph()
  })

  if (progress >= 1) {
    display.value = target.value
    stop()
  }
}

const start = () => {
  stop()
  reset()
  timer = setInterval(step, props.intervalMs)
}

const stop = () => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(() => {
  start()
})

onBeforeUnmount(() => {
  stop()
})

watch(
  () => props.text,
  () => {
    start()
  }
)

const variantClass = computed(() => {
  if (props.variant === 'mono') return 'gradient-mono'
  if (props.variant === 'static') return 'static-dark'
  return 'gradient-neon'
})
</script>

<template>
  <span class="scramble-title" :class="variantClass" :aria-label="text">
    {{ display.join('') }}
  </span>
</template>

<style scoped>
.scramble-title {
  display: inline-block;
}

.gradient-neon {
  background: linear-gradient(120deg, #16f2b3, #7c3aed, #06b6d4, #f472b6);
  background-size: 250% 250%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: textShift 3.5s ease-in-out infinite;
}

@keyframes textShift {
  0% {
    background-position: 0% 0%;
  }
  50% {
    background-position: 100% 100%;
  }
  100% {
    background-position: 0% 0%;
  }
}

.gradient-mono {
  background: linear-gradient(120deg, #111827, #9ca3af, #111827);
  background-size: 220% 220%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: textShift 3.5s ease-in-out infinite;
}

.static-dark {
  color: #0f172a;
}
</style>
