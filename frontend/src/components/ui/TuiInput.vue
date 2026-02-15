<script setup>
const props = defineProps({
  label: String,
  hint: String,
  placeholder: {
    type: String,
    default: ''
  },
  modelValue: {
    type: [String, Number],
    default: ''
  },
  type: {
    type: String,
    default: 'text'
  }
})

const emit = defineEmits(['update:modelValue'])

const onInput = (event) => {
  emit('update:modelValue', event.target.value)
}
</script>

<template>
  <label class="flex flex-col gap-2 text-sm text-[var(--text)]">
    <div class="flex items-center justify-between">
      <span class="text-xs uppercase tracking-wider text-[var(--muted)]">{{ label }}</span>
      <span v-if="hint" class="text-xs text-[var(--muted)]">{{ hint }}</span>
    </div>
    <div class="breathing-ring">
      <input
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        class="w-full rounded-md border border-[var(--border-strong)] bg-white px-3 py-2 text-[var(--text)] focus:border-[var(--text)] focus:outline-none focus:ring-2 focus:ring-[rgba(31,31,31,0.12)]"
        @input="onInput"
      />
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

.breathing-ring > input {
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
