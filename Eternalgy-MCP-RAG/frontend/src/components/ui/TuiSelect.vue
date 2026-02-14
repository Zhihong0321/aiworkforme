<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: String,
  hint: String,
  modelValue: {
    type: String,
    default: ''
  },
  options: {
    type: Array,
    default: () => []
  },
  placeholder: {
    type: String,
    default: 'Select'
  }
})

const emit = defineEmits(['update:modelValue'])

const hasValue = computed(() => !!props.modelValue)

const onChange = (event) => {
  emit('update:modelValue', event.target.value)
}
</script>

<template>
  <label class="flex flex-col gap-2 text-sm text-[var(--text)]">
    <div class="flex items-center justify-between">
      <span class="text-xs uppercase tracking-wider text-[var(--muted)]">{{ label }}</span>
      <span v-if="hint" class="text-xs text-[var(--muted)]">{{ hint }}</span>
    </div>
    <div class="relative breathing-ring">
      <select
        class="w-full appearance-none rounded-md border border-[var(--border-strong)] bg-white px-3 py-2 pr-9 text-[var(--text)] focus:border-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[rgba(31,31,31,0.1)]"
        :value="modelValue"
        @change="onChange"
      >
        <option disabled value="">{{ placeholder }}</option>
        <option v-for="option in options" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <span
        class="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[var(--muted)] transition"
        :class="hasValue ? 'opacity-80' : 'opacity-60'"
      >
        ▾
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
