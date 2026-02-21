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
    <div class="relative">
      <select
        :class="[
          'w-full appearance-none rounded-xl border px-4 py-3 pr-10 text-sm transition-all focus:outline-none focus:ring-2',
          dark 
            ? 'bg-white/5 border-white/10 text-white focus:border-white/30 focus:ring-white/10' 
            : 'bg-white border-[var(--border-strong)] text-[var(--text)] focus:border-[var(--accent)] focus:ring-[rgba(29,78,216,0.15)]'
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
