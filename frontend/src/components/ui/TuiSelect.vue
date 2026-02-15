<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: String,
  hint: String,
  modelValue: {
    type: [String, Number],
    default: ''
  },
  options: {
    type: Array,
    default: () => []
  },
  placeholder: {
    type: String,
    default: 'Select'
  },
  dark: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const hasValue = computed(() => !!props.modelValue)

const onChange = (event) => {
  emit('update:modelValue', event.target.value)
}
</script>

<template>
  <label :class="['flex flex-col gap-2 text-sm', dark ? 'text-white' : 'text-[var(--text)]']">
    <div class="flex items-center justify-between">
      <span :class="['text-[10px] font-bold uppercase tracking-widest', dark ? 'text-white/40' : 'text-[var(--muted)]']">{{ label }}</span>
      <span v-if="hint" :class="['text-xs', dark ? 'text-white/40' : 'text-[var(--muted)]']">{{ hint }}</span>
    </div>
    <div class="relative breathing-ring">
      <select
        :class="[
          'w-full appearance-none rounded-xl border px-4 py-3 pr-10 text-sm transition-all focus:outline-none focus:ring-2',
          dark 
            ? 'bg-white/5 border-white/10 text-white focus:border-white/30 focus:ring-white/10' 
            : 'bg-white border-[var(--border-strong)] text-[var(--text)] focus:border-[var(--text)] focus:ring-[rgba(31,31,31,0.1)]'
        ]"
        :value="modelValue"
        @change="onChange"
      >
        <option disabled value="">{{ placeholder }}</option>
        <option v-for="option in options" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <span
        :class="[
          'pointer-events-none absolute inset-y-0 right-4 flex items-center transition text-[10px]',
          dark ? 'text-white/40' : 'text-[var(--muted)]',
          hasValue ? 'opacity-100' : 'opacity-40'
        ]"
      >
        ▼
      </span>
    </div>
  </label>
</template>

<style scoped>
.breathing-ring {
  position: relative;
  border-radius: inherit;
}

.breathing-ring::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: inherit;
  background: linear-gradient(120deg, rgba(255, 130, 0, 0.25), rgba(43, 60, 74, 0.25), rgba(0, 0, 0, 0.1), rgba(255, 130, 0, 0.25));
  background-size: 220% 220%;
  opacity: 0;
  z-index: 0;
  filter: blur(0.5px);
  transition: opacity 0.3s ease;
  animation: breatheGradient 3s ease-in-out infinite;
  pointer-events: none;
}

.breathing-ring:focus-within::after {
  opacity: 0.65;
}

.breathing-ring > select,
.breathing-ring > span {
  position: relative;
  z-index: 1;
}

@keyframes breatheGradient {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}
</style>
