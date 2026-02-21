<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  length: {
    type: Number,
    default: 12
  },
  intervalMs: {
    type: Number,
    default: 1000 / 60
  },
  label: {
    type: String,
    default: 'loading'
  },
  state: {
    type: String,
    default: 'loading' // loading | done
  },
  doneText: {
    type: String,
    default: 'DONE'
  },
  finishDuration: {
    type: Number,
    default: 500 // ms to resolve into final text
  },
  keySeed: {
    type: [String, Number],
    default: 0
  }
})

const glyphs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%&'
const text = ref([])
let churnTimer = null
let settleTimer = null
let settlePlan = []
let settleStarted = 0
const pillLabel = computed(() => (props.state === 'done' ? 'done' : 'live'))

const randomGlyph = () => glyphs[Math.floor(Math.random() * glyphs.length)] || 'X'

const baseLength = (targetLen) => Math.max(props.length, targetLen || 0)

const churn = (len) => {
  const next = []
  for (let i = 0; i < len; i += 1) {
    next.push(randomGlyph())
  }
  text.value = next
}

const stopAll = () => {
  if (churnTimer) {
    clearInterval(churnTimer)
    churnTimer = null
  }
  if (settleTimer) {
    clearInterval(settleTimer)
    settleTimer = null
  }
}

const startLoading = () => {
  stopAll()
  const len = baseLength(props.doneText.length)
  churn(len)
  churnTimer = setInterval(() => churn(len), props.intervalMs)
}

const startSettling = () => {
  stopAll()
  const finalChars = (props.doneText || 'DONE').split('')
  const len = baseLength(finalChars.length)
  settlePlan = Array.from({ length: len }, () => Math.random() * props.finishDuration)
  // Ensure at least one character lands exactly at the end of the window
  if (len > 0) {
    const idx = Math.floor(Math.random() * len)
    settlePlan[idx] = props.finishDuration
  }
  settleStarted = performance.now()
  churn(len)
  settleTimer = setInterval(() => {
    const elapsed = performance.now() - settleStarted
    const next = []
    let allResolved = true
    for (let i = 0; i < len; i += 1) {
      const targetChar = finalChars[i] || ''
      if (elapsed >= settlePlan[i]) {
        next.push(targetChar)
      } else {
        allResolved = false
        next.push(randomGlyph())
      }
    }
    text.value = next
    if (allResolved && elapsed >= props.finishDuration) {
      text.value = finalChars
      stopAll()
    }
  }, props.intervalMs)
}

onMounted(() => {
  if (props.state === 'done') {
    startSettling()
  } else {
    startLoading()
  }
})

onUnmounted(() => {
  stopAll()
})

watch(
  () => props.length,
  () => {
    if (props.state === 'loading') startLoading()
  }
)

watch(
  () => props.state,
  (val) => {
    if (val === 'done') {
      startSettling()
    } else {
      startLoading()
    }
  }
)

watch(
  () => props.doneText,
  (val) => {
    if (props.state === 'done') {
      startSettling()
    }
  }
)

watch(
  () => props.keySeed,
  () => {
    if (props.state === 'done') {
      startSettling()
    } else {
      startLoading()
    }
  }
)
</script>

<template>
  <div class="tui-loader relative rounded-xl p-4">
    <div class="relative flex items-center justify-between gap-3 font-mono">
      <div class="flex flex-col">
        <span class="text-[11px] uppercase tracking-[0.2em] text-slate-600">{{ label }}</span>
        <span class="mt-1 text-xl font-semibold gradient-text">{{ text.join('') }}</span>
      </div>
      <span class="rounded-md border border-slate-900 bg-slate-50 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-900">
        {{ pillLabel }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.gradient-text {
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
</style>
